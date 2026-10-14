import argparse
from dataclasses import fields, replace
from pathlib import Path
import json
from .contracts import Contract
from .examples import EXAMPLES, get_example
from .kernel import audit
from .reporting import LABELS, compare_reports, read_report, save_report, verify_payload

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "artifacts"


def describe(report):
    print(f"6D: {LABELS[report['verdict']]}")
    print(report["summary"])
    for check in report["checks"]:
        print(f"  {check['id']}: {check['status']}")
        if "observed_orders" in check:
            print("  Measured refinement orders: "+", ".join("unresolved" if p is None else f"{p:.4f}" for p in check["observed_orders"]))
    print(f"Not tested: {len(report['not_tested'])} explicit exclusions.")
    print(f"Execution: local curated functions. Provider: {report['model_mode']}. Live model calls: {report['live_model_calls']}.")
    if 'investigation' in report:
        print('Investigation:', report['investigation']['state'])
        if report['investigation']['error']:
            print(report['investigation']['error'])


def reconstruct_contract(record):
    allowed = {field.name for field in fields(Contract)}
    if set(record) != allowed:
        raise ValueError("The report's contract schema differs from this implementation.")
    record = dict(record)
    record["refinement_steps"] = tuple(record["refinement_steps"])
    return Contract(**record)


def describe_project(review):
    print(f"6D project review: {review['review_status']}")
    print(f"Project: {review['project']['name']} / revision {review['revision']}")
    for identity, finding in review['findings'].items():
        print(f"  {identity}: {finding['status']} - {finding['reason']}")
    print("Coverage: bounded declared models and requirements; physical validity and whole-mission readiness are not established.")
    print("Provider: disabled. Live model calls: 0. Launch authorization: not issued.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="6D engineering evidence and numerical review; supported local inputs only.")
    commands = parser.add_subparsers(dest="command",required=True)
    demo = commands.add_parser("demo",help="Generate all five curated demonstrations; no human sign-off is claimed.")
    demo.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    single = commands.add_parser("audit",help="Audit one reviewed curated example.")
    single.add_argument("--case",choices=EXAMPLES,default="verlet_correct")
    single.add_argument("--accept-contract",action="store_true",help="Acknowledge the displayed example contract; no authenticated signature.")
    single.add_argument("--radius",type=float,help="Change the synthetic reference radius in metres, creating a different contract hash.")
    single.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    investigate = commands.add_parser('investigate', help='Run a bounded structured tool investigation; fixture is the default.')
    investigate.add_argument('--case', choices=EXAMPLES, default='verlet_correct')
    investigate.add_argument('--provider', choices=('fixture', 'token-factory'), default='fixture')
    investigate.add_argument('--accept-contract', action='store_true')
    investigate.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    commands.add_parser('provider-status', help='Inspect local configuration gates without contacting the provider.')
    project = commands.add_parser('project-review', help='Review a JSON project using maintained bounded engineering calculations; no uploaded code runs.')
    project.add_argument('project', type=Path)
    project.add_argument('--output', type=Path, default=DEFAULT_OUTPUT / 'projects')
    project.add_argument('--compare-with', type=Path, help='Compare this fresh review against a saved review of the same project.')
    project_compare = commands.add_parser('project-compare', help='Compare explicit evidence dependencies between saved project reviews.')
    project_compare.add_argument('old', type=Path)
    project_compare.add_argument('new', type=Path)
    project_verify = commands.add_parser('project-verify', help='Check a project review snapshot for internal consistency; not an authenticated signature.')
    project_verify.add_argument('review', type=Path)
    project_demo = commands.add_parser('project-demo', help='Run constructed baseline/change/missing-evidence demonstrations without inference.')
    project_demo.add_argument('--output', type=Path, default=DEFAULT_OUTPUT / 'projects')
    show = commands.add_parser("contract",help="Display the exact assumptions before running an audit.")
    show.add_argument("--case",choices=EXAMPLES,default="verlet_correct")
    verify = commands.add_parser("verify",help="Check a saved record's digest. This is not a signature verification.")
    verify.add_argument("report",type=Path)
    reproduce = commands.add_parser("reproduce",help="Rerun a saved record using its original contract and matching sources.")
    reproduce.add_argument("report",type=Path)
    reproduce.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    compare = commands.add_parser("compare",help="Compare contracts, source versions and evidence verdicts.")
    compare.add_argument("old",type=Path);compare.add_argument("new",type=Path)
    serve = commands.add_parser("serve",help="Open a local-only review interface.")
    serve.add_argument("--port",type=int,default=8766)
    args = parser.parse_args(argv)
    try:
        if args.command.startswith('project-'):
            from .engineering import evaluate_models
            from .lifecycle import compare_reviews, review_project, validate_project
            from .project_io import read_json, read_review, save_review
            if args.command == 'project-verify':
                read_review(args.review)
                print('Project snapshot, findings and fingerprints are internally consistent. No authenticated signature is claimed.')
            elif args.command == 'project-compare':
                print(json.dumps(compare_reviews(read_review(args.old), read_review(args.new)), indent=2))
            elif args.command == 'project-demo':
                from .project_examples import example_projects
                previous = None
                for label, record in example_projects().items():
                    reviewed = validate_project(record)
                    report = review_project(reviewed, evaluate_models(reviewed))
                    path = save_review(report, args.output)
                    print(f'Constructed example: {label}')
                    describe_project(report)
                    print('Review JSON:', path)
                    if previous is not None:
                        print(json.dumps(compare_reviews(previous, report), indent=2))
                    previous = report
            else:
                reviewed = validate_project(read_json(args.project))
                report = review_project(reviewed, evaluate_models(reviewed))
                comparison = None
                if args.compare_with:
                    comparison = compare_reviews(read_review(args.compare_with), report)
                path = save_review(report, args.output)
                describe_project(report)
                print('Review JSON:', path)
                if comparison is not None:
                    print(json.dumps(comparison, indent=2))
                return 0 if report['review_status'] == 'supported_requirements_met' else 1 if report['review_status'] == 'requirements_not_met' else 2
            return 0
        elif args.command == 'provider-status':
            from .providers import provider_status
            print(json.dumps(provider_status(ROOT), indent=2))
        elif args.command == 'investigate':
            from .investigation import investigate as run_investigation
            from .providers import make_provider
            example = get_example(args.case)
            if not args.accept_contract:
                print(json.dumps(example.contract.record(), indent=2))
                print('Review this contract, then rerun with --accept-contract.')
                return 2
            report = run_investigation(example, make_provider(args.provider, ROOT),
                review={'mode': 'operator_acknowledged_cli', 'human_acceptance_claimed': True, 'authenticated_identity': False})
            paths = save_report(report, args.output)
            describe(report); print('Evidence JSON:', paths['json_path'])
            return 0 if report['investigation']['state'] in ('completed', 'blocked_contract') else 2
        elif args.command == "serve":
            from .server import serve_local
            serve_local(args.port,DEFAULT_OUTPUT)
        elif args.command == "contract":
            c = get_example(args.case).contract
            print(json.dumps(c.record(),indent=2));print("Contract SHA-256:",c.sha256)
        elif args.command == "demo":
            for example in EXAMPLES.values():
                report = audit(example)
                paths = save_report(report,args.output)
                describe(report);print("Evidence JSON:",paths["json_path"]);print()
        elif args.command == "audit":
            example = get_example(args.case)
            c = example.contract if args.radius is None else replace(example.contract,radius=args.radius)
            if not args.accept_contract:
                print(json.dumps(c.record(),indent=2))
                print("Review this contract, then rerun with --accept-contract.")
                return 2
            report = audit(example,contract=c,review={"mode":"operator_acknowledged_cli", "human_acceptance_claimed":True,"authenticated_identity":False})
            paths = save_report(report,args.output)
            describe(report);print("Evidence JSON:",paths["json_path"])
        elif args.command == "verify":
            read_report(args.report)
            print("Recorded digest and contract digest match. No authenticated signature is claimed.")
        elif args.command == "compare":
            print(json.dumps(compare_reports(read_report(args.old),read_report(args.new)),indent=2))
        elif args.command == "reproduce":
            original = read_report(args.report)
            example = get_example(original["example_id"])
            c = reconstruct_contract(original["contract"])
            current = audit(example,contract=c,review={"mode":"reproduction", "human_acceptance_claimed":False})
            if current["candidate_source"]["source_sha256"]!=original["candidate_source"]["source_sha256"] or current["verification_sources"]!=original["verification_sources"]:
                raise ValueError("Source versions have changed. This run cannot reproduce the recorded implementation.")
            if current["audit_id"] != original["audit_id"]:
                raise ValueError("The recorded experiment result was not reproduced. Inspect runtime and evidence differences.")
            paths = save_report(current,args.output)
            print("The audit identity and numerical evidence were reproduced.");print(paths["json_path"])
        return 0
    except (ValueError, OSError) as exc:
        print(f"6D: {exc}")
        return 2
