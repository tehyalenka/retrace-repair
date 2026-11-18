import unittest
from two_phase import TwoPhaseCoordinator, Participant, ParticipantState

class Public(unittest.TestCase):
    def test_unanimous_commit(self):
        p1 = Participant("db1")
        p2 = Participant("db2")
        coord = TwoPhaseCoordinator([p1, p2])

        success = coord.execute_transaction("tx-100")
        self.assertTrue(success)
        self.assertEqual(p1.state, ParticipantState.COMMITTED)
        self.assertEqual(p2.state, ParticipantState.COMMITTED)
        self.assertEqual(coord.transaction_logs["tx-100"], "COMMITTED")

    def test_single_failure_aborts_all_prepared_participants(self):
        p1 = Participant("db1")
        p2 = Participant("db2", should_fail_prepare=True)
        coord = TwoPhaseCoordinator([p1, p2])

        success = coord.execute_transaction("tx-101")
        self.assertFalse(success)
        # Even though p1 voted yes and prepared, coordinator failure MUST abort p1
        self.assertEqual(p1.state, ParticipantState.ABORTED)
        self.assertEqual(p2.state, ParticipantState.ABORTED)
        self.assertEqual(coord.transaction_logs["tx-101"], "ABORTED")
