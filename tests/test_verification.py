from dataclasses import replace
from pathlib import Path
import copy
import json
import math
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from sixd.cli import main
from sixd.contracts import Contract, digest
from sixd.examples import EXAMPLES, Example, attractive_acceleration, euler_step, verlet_step
from sixd.kernel import audit, force_experiment, normalized_state_error, reversal_experiment
from sixd.reporting import compare_reports, read_report, save_report, verify_payload


def must_not_run(*args):
    raise AssertionError("An ambiguous contract must abstain before execution.")


def nonfinite_acceleration(*args):
    return math.nan, 0.0


def negative_x_force_error(x, y, mu):
    # Held-out coordinate-sign defect: correct in the original first-quadrant probes.
    inverse_r3 = 1.0/math.hypot(x,y)**3
    return -mu*abs(x)*inverse_r3, -mu*y*inverse_r3


def midpoint_step(state, dt, mu, acceleration):
    # Correct explicit RK2 midpoint; order alone cannot identify velocity Verlet.
    x,y,vx,vy = state
    ax,ay = acceleration(x,y,mu)
    mx,my = x+0.5*dt*vx,y+0.5*dt*vy
    mvx,mvy = vx+0.5*dt*ax,vy+0.5*dt*ay
    max_,may = acceleration(mx,my,mu)
    return x+dt*mvx,y+dt*mvy,vx+dt*max_,vy+dt*may


def unsampled_force_error(x, y, mu):
    ax,ay = attractive_acceleration(x,y,mu)
    factor = 1.1 if 0.11 < math.atan2(y,x) < 0.17 else 1.0
    return factor*ax,factor*ay


def forward_only_step(state, dt, mu, acceleration):
    if dt < 0:
        return math.nan,0.0,0.0,0.0
    return verlet_step(state,dt,mu,acceleration)


class VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = {key:audit(example) for key,example in EXAMPLES.items()}
        (ROOT/"work").mkdir(exist_ok=True)

    def test_verlet_quarter_orbit_matches_independent_geometry(self):
        c = Contract()
        state=c.initial_state()
        dt=c.period/4096
        for _ in range(1024):
            state=verlet_step(state,dt,c.mu,attractive_acceleration)
        self.assertLess(abs(state[0])/c.radius,2e-6)
        self.assertLess(abs(state[1]/c.radius-1),2e-6)
        self.assertLess(abs(state[3])/math.sqrt(c.mu/c.radius),2e-6)

    def test_verlet_time_reversal_recovers_initial_state(self):
        c=Contract(phase_radians=math.pi/7)
        initial=c.initial_state();state=initial;dt=c.period/4096
        for _ in range(777):
            state=verlet_step(state,dt,c.mu,attractive_acceleration)
        for _ in range(777):
            state=verlet_step(state,-dt,c.mu,attractive_acceleration)
        self.assertLess(normalized_state_error(state,initial,c),1e-11)

    def test_supported_correct_solver_has_second_order_evidence(self):
        report=self.reports["verlet_correct"]
        self.assertEqual(report["verdict"],"no_defect_found_in_scope")
        refinement=report["checks"][1]
        self.assertTrue(all(1.95<p<2.05 for p in refinement["observed_orders"]))
        errors=[r["max_state_error"] for r in refinement["runs"]]
        self.assertLess(errors[-1],errors[0]/50)
        self.assertTrue(report["not_tested"])
        self.assertEqual([check["id"] for check in report["checks"]],
                         ["central_force_reference","analytic_reference_refinement","method_time_reversal"])
        self.assertEqual(report["checks"][2]["status"],"pass")

    def test_outward_force_fails_reference_across_all_probes(self):
        report=self.reports["force_sign_error"]
        self.assertEqual(report["verdict"],"defect_likely")
        probes=report["checks"][0]["probes"]
        self.assertEqual(len(probes),72)
        self.assertTrue(all(abs(p["relative_residual"]-2)<1e-10 for p in probes))
        self.assertEqual(report["findings"][0]["source_function"],"outward_acceleration")

    def test_negative_coordinate_force_defect_is_localized_by_reference_evidence(self):
        example=replace(EXAMPLES["verlet_correct"],acceleration=negative_x_force_error)
        report=audit(example)
        self.assertEqual(report["verdict"],"defect_likely")
        self.assertEqual(report["findings"][0]["kind"],"force_model_mismatch")
        self.assertEqual(report["findings"][0]["source_function"],"negative_x_force_error")
        probes=report["checks"][0]["probes"]
        negative=[p for p in probes if p["position_m"][0]<0]
        positive=[p for p in probes if p["position_m"][0]>=0]
        self.assertTrue(all(p["relative_residual"]>1 for p in negative))
        self.assertTrue(all(p["relative_residual"]<1e-10 for p in positive))
        self.assertEqual(report["contract_sha256"],example.contract.sha256)
        verify_payload(report)

    def test_force_probes_cover_each_axis_quadrant_and_parameter_scale(self):
        check=force_experiment(EXAMPLES["verlet_correct"],Contract())
        self.assertEqual(check["status"],"pass")
        probes=check["probes"]
        for mu_factor in (0.5,1.0,2.0):
            for radius_factor in (0.7,1.0,1.4):
                positions=[p["position_m"] for p in probes
                           if p["mu_factor"]==mu_factor and p["radius_factor"]==radius_factor]
                self.assertTrue(any(x>0 and y==0 for x,y in positions))
                self.assertTrue(any(x<0 and y==0 for x,y in positions))
                self.assertTrue(any(x==0 and y>0 for x,y in positions))
                self.assertTrue(any(x==0 and y<0 for x,y in positions))
                self.assertEqual({(x>0,y>0) for x,y in positions if x!=0 and y!=0},
                                 {(True,True),(False,True),(False,False),(True,False)})

    def test_different_second_order_stepper_fails_declared_verlet_property(self):
        example=replace(EXAMPLES["verlet_correct"],step=midpoint_step)
        report=audit(example)
        self.assertEqual(report["checks"][0]["status"],"pass")
        self.assertEqual(report["checks"][1]["status"],"pass")
        self.assertEqual(report["checks"][2]["status"],"fail")
        self.assertEqual(report["verdict"],"defect_likely")
        finding=report["findings"][0]
        self.assertEqual(finding["kind"],"declared_method_property_mismatch")
        self.assertEqual(finding["evidence_ids"],["method_time_reversal"])
        self.assertNotIn("source_function",finding)
        self.assertIn("algorithm identity",finding["localization"])
        verify_payload(report)

    def test_reversal_roundoff_policy_handles_rotated_and_rescaled_correct_inputs(self):
        for phase,radius,mu in ((math.pi,8e6,3.986004418e14),
                                (7*math.pi/5,1e4,4e8),(-math.pi/7,3e7,8e13)):
            with self.subTest(phase=phase,radius=radius,mu=mu):
                c=Contract(phase_radians=phase,radius=radius,mu=mu)
                report=audit(EXAMPLES["verlet_correct"],contract=c)
                self.assertEqual(report["verdict"],"no_defect_found_in_scope")
                check=report["checks"][2]
                self.assertEqual(len(check["probes"]),9)
                self.assertEqual(check["status"],"pass")
                self.assertTrue(check["comparison_assumptions"])
                for p in check["probes"]:
                    expected=128*sys.float_info.epsilon*(p["forward_steps"]+p["reverse_steps"]+1)
                    self.assertEqual(p["acceptance_threshold"],expected)
                    self.assertLess(p["normalized_return_error"],expected)
                self.assertEqual(report["contract_sha256"],c.sha256)
                verify_payload(report)

    def test_unsampled_force_defect_does_not_get_asserted_as_step_defect(self):
        example=replace(EXAMPLES["verlet_correct"],acceleration=unsampled_force_error)
        report=audit(example)
        self.assertEqual(report["checks"][0]["status"],"pass")
        self.assertEqual(report["checks"][1]["status"],"fail")
        self.assertEqual(report["verdict"],"defect_likely")
        finding=report["findings"][0]
        self.assertEqual(finding["kind"],"declared_order_mismatch")
        self.assertNotIn("source_function",finding)
        self.assertIn("unsampled force defects",finding["localization"])
        self.assertIn("unsampled_force_error",finding["source_functions"])

    def test_reversal_nonfinite_result_abstains_with_completed_checks_retained(self):
        example=replace(EXAMPLES["verlet_correct"],step=forward_only_step)
        report=audit(example)
        self.assertEqual(report["verdict"],"inconclusive")
        self.assertEqual([c["status"] for c in report["checks"]],["pass","pass"])
        self.assertEqual(report["findings"][0]["kind"],"experiment_execution_failure")
        json.dumps(report,allow_nan=False)
        verify_payload(report)

    def test_euler_drift_does_not_trigger_a_false_force_accusation(self):
        report=self.reports["euler_method_limit"]
        self.assertEqual(report["verdict"],"method_limitation")
        self.assertEqual(len(report["checks"]),2)
        self.assertEqual(report["checks"][0]["status"],"pass")
        runs=report["checks"][1]["runs"]
        self.assertGreater(runs[-1]["final_energy_change_fraction"],0)
        self.assertLess(runs[-1]["max_state_error"],runs[0]["max_state_error"])
        self.assertTrue(all(0.9<p<1.1 for p in report["checks"][1]["rotated_initial_condition_orders"]))

    def test_same_euler_code_conflicts_with_a_second_order_contract(self):
        report=self.reports["wrong_order"]
        self.assertEqual(report["verdict"],"defect_likely")
        self.assertEqual(report["checks"][0]["status"],"pass")
        self.assertEqual(report["findings"][0]["kind"],"declared_order_mismatch")

    def test_ambiguous_contract_never_runs_candidate_functions(self):
        example=Example("ambiguous","No frame","",must_not_run,must_not_run,Contract(frame="unspecified"))
        report=audit(example)
        self.assertEqual(report["verdict"],"inconclusive")
        self.assertEqual(report["checks"],[])

    def test_unknown_units_are_not_inferred(self):
        report=audit(EXAMPLES["verlet_correct"],contract=Contract(position_unit="km"))
        self.assertEqual(report["verdict"],"inconclusive")
        self.assertEqual(report["checks"],[])

    def test_acceptance_thresholds_cannot_be_softened(self):
        report=audit(EXAMPLES["force_sign_error"],contract=Contract(force_relative_tolerance=3.0))
        self.assertEqual(report["verdict"],"inconclusive")
        self.assertEqual(report["checks"],[])

    def test_nonfinite_results_abstain_and_remain_serializable(self):
        example=replace(EXAMPLES["verlet_correct"],acceleration=nonfinite_acceleration)
        report=audit(example)
        self.assertEqual(report["verdict"],"inconclusive")
        self.assertEqual(report["findings"][0]["kind"],"experiment_execution_failure")
        json.dumps(report,allow_nan=False)
        verify_payload(report)

    def test_repeated_run_has_same_audit_identity_and_evidence(self):
        first=self.reports["verlet_correct"];second=audit(EXAMPLES["verlet_correct"])
        self.assertEqual(first["audit_id"],second["audit_id"])
        self.assertEqual(first["checks"],second["checks"])

    def test_change_is_a_new_contract_and_scope(self):
        first=self.reports["verlet_correct"]
        second=audit(EXAMPLES["verlet_correct"],contract=Contract(radius=8e6))
        changes=compare_reports(first,second)
        self.assertEqual(changes["contract_changes"][0]["field"],"radius")
        self.assertNotEqual(first["contract_sha256"],second["contract_sha256"])
        self.assertNotEqual(first["audit_id"],second["audit_id"])

    def test_record_edit_is_detected(self):
        changed=copy.deepcopy(self.reports["verlet_correct"])
        changed["checks"][0]["max_relative_residual"]=1
        with self.assertRaises(ValueError):verify_payload(changed)

    def test_rehashing_edit_without_updating_identity_is_detected(self):
        changed=copy.deepcopy(self.reports["verlet_correct"])
        changed["verdict"]="defect_likely"
        changed["report_payload_sha256"]=digest({k:v for k,v in changed.items() if k!="report_payload_sha256"})
        with self.assertRaises(ValueError):verify_payload(changed)

    def test_snapshots_are_exclusive_and_cli_reproduces(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"work") as directory:
            first=save_report(self.reports["verlet_correct"],directory)
            with self.assertRaises(FileExistsError):save_report(self.reports["verlet_correct"],directory)
            self.assertEqual(read_report(first["json_path"])["verdict"],"no_defect_found_in_scope")
            self.assertEqual(main(["reproduce",first["json_path"],"--output",directory]),0)
            self.assertEqual(len(list(Path(directory).glob("*.json"))),2)


if __name__=="__main__":unittest.main()
