"""Wire read menus express the decoder's no-payload contract."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from sixd.project_investigation import ProjectActionAdapter, _tools
from sixd.whole_project_investigation import WholeProjectActionAdapter
from sixd.providers import ProviderError
from sixd.evidence_facts import PROSE_POLICY


MESSAGES = [{'role': 'system', 'content': 'Read frozen evidence.'},
            {'role': 'user', 'content': '{}'}]


def envelope(action, *, ids=None, summary=''):
    return {'role': 'assistant', 'content': None, 'tool_calls': [{
        'id': 'provider-selection', 'type': 'function', 'function': {
            'name': 'select_next_action', 'arguments': json.dumps({
                'action': action, 'evidence_ids': [] if ids is None else ids,
                'summary': summary})}}]}


class ReadActionWireSchemaTests(unittest.TestCase):
    def menus(self):
        yield ProjectActionAdapter, _tools(['read_requirement', 'read_model', 'read_changes'], {})
        yield ProjectActionAdapter, _tools(['recheck_model'], {})
        yield WholeProjectActionAdapter, [{'function': {'name': n, 'parameters': {}}}
            for n in ('read_project', 'read_dependencies', 'read_changes')]

    def test_read_only_schema_requires_empty_citations_and_summary(self):
        for adapter, menu in self.menus():
            with self.subTest(adapter=adapter.__name__, menu=menu[0]['function']['name']):
                _, wire, _ = adapter.build_action_request(MESSAGES, menu)
                schema = wire[0]['function']['parameters']
                fields = schema['properties']
                self.assertEqual(fields['evidence_ids']['maxItems'], 0)
                self.assertEqual(fields['summary']['enum'], [''])
                self.assertEqual(set(schema['required']), {'action', 'summary', 'evidence_ids'})
                self.assertFalse(schema['additionalProperties'])

    def test_exact_read_examples_round_trip_to_parameterless_kernel_calls(self):
        for adapter, menu in self.menus():
            messages, _, _ = adapter.build_action_request(MESSAGES, menu)
            hints = json.loads(messages[-1]['content'])
            examples = hints.get('valid_read_selections') or [hints['read_example']]
            self.assertTrue(examples)
            for example in examples:
                self.assertEqual(example['evidence_ids'], [])
                self.assertEqual(example['summary'], '')
                decoded, problem, shape, origin = adapter.decode_action_response(
                    envelope(example['action']), menu, internal_call_id='runner')
                self.assertIsNone(problem)
                self.assertEqual(json.loads(decoded['tool_calls'][0]['function']['arguments']), {})
                self.assertEqual((shape, origin), ('native_tool_call', 'provider'))

    def test_nonempty_read_payload_is_still_rejected_not_stripped_or_retried(self):
        for adapter, menu in self.menus():
            name = menu[0]['function']['name']
            for values in ({'summary': 'Claiming unseen evidence is acceptable.'},
                           {'ids': ['unseen-evidence']},
                           {'ids': ['unseen-evidence'], 'summary': 'Ignored inputs?'}):
                with self.subTest(adapter=adapter.__name__, values=values):
                    with self.assertRaises(ProviderError) as caught:
                        adapter.decode_action_response(envelope(name, **values), menu,
                                                       internal_call_id='runner')
                    self.assertEqual(caught.exception.diagnostic['selection_rejection'],
                                     'read_payload_not_empty')

    def test_finish_and_mixed_menus_keep_final_summary_contract(self):
        evidence = {'requirement:thermal': {}, 'model:thermal': {}}
        for adapter in (ProjectActionAdapter, WholeProjectActionAdapter):
            for names in (['finish'], ['read_changes', 'finish']):
                menu = _tools(names, evidence)
                _, wire, _ = adapter.build_action_request(MESSAGES, menu)
                fields = wire[0]['function']['parameters']['properties']
                self.assertNotIn('maxItems', fields['evidence_ids'])
                self.assertNotIn('enum', fields['summary'])
                decoded, problem, *_ = adapter.decode_action_response(
                    envelope('finish', ids=list(evidence), summary='Review the recorded model limits.'),
                    menu, internal_call_id='runner')
                self.assertIsNone(problem)
                self.assertEqual(decoded['tool_calls'][0]['function']['name'], 'finish')

    def test_current_finish_schema_guides_paragraphs_without_constraining_legacy_numeric_prose(self):
        menu = _tools(['finish'], {'requirement:thermal': {}, 'model:thermal': {}})
        _, wire, _ = ProjectActionAdapter.build_action_request(MESSAGES, menu)
        field = wire[0]['function']['parameters']['properties']['summary']
        self.assertEqual(field['pattern'], r'^[^0-9]*$')
        self.assertEqual(field['minLength'], 100)
        legacy = [MESSAGES[0], {'role':'user', 'content':json.dumps({'explanation_policy':PROSE_POLICY})}]
        _, wire, _ = ProjectActionAdapter.build_action_request(legacy, menu)
        field = wire[0]['function']['parameters']['properties']['summary']
        self.assertNotIn('pattern', field)
        self.assertNotIn('minLength', field)

    def test_whole_project_finish_uses_plain_string_but_local_guards_remain_active(self):
        from sixd.whole_project_investigation import _quality
        menu = _tools(['finish'], {'project':{}, 'dependencies':{}, 'changes':{}})
        _, wire, _ = WholeProjectActionAdapter.build_action_request(MESSAGES, menu)
        field=wire[0]['function']['parameters']['properties']['summary']
        self.assertEqual(field['type'],'string')
        self.assertNotIn('pattern',field)
        self.assertNotIn('minLength',field)
        self.assertNotIn('enum',field)
        findings={'thermal_limit':{'status':'not_met'}}
        clean=('This is a bounded review of the saved evidence; excluded effects remain unassessed. '
               'Inspect the thermal assumptions before extending this component finding to the wider design.')
        self.assertTrue(_quality(clean,findings,linked_sources={})['accepted'])
        self.assertIn('numerical_prose',_quality(clean+' This is revision 2.',findings,linked_sources={})['blocked_codes'])
        self.assertIn('uncaptured_linked_reference',_quality(clean+' Review the linked NASA thermal control reference.',findings,linked_sources={})['blocked_codes'])
        self.assertIn('scope_missing',_quality('Inspect the thermal model and obtain control analysis.',findings)['blocked_codes'])


if __name__ == '__main__':
    unittest.main()
