import unittest
from two_phase import TwoPhaseCoordinator, Participant, ParticipantState

class CrashingParticipant(Participant):
    def prepare(self, tx_id):
        raise ConnectionResetError("network partition during prepare")

class Heldout(unittest.TestCase):
    def test_exception_in_prepare_triggers_abort(self):
        p1 = Participant("db1")
        p2 = CrashingParticipant("db2")
        p3 = Participant("db3")
        coord = TwoPhaseCoordinator([p1, p2, p3])

        success = coord.execute_transaction("tx-fail")
        self.assertFalse(success)
        self.assertEqual(p1.state, ParticipantState.ABORTED)
        self.assertEqual(p3.state, ParticipantState.ABORTED)
        self.assertEqual(coord.transaction_logs["tx-fail"], "ABORTED")

    def test_empty_participants_raises_value_error(self):
        coord = TwoPhaseCoordinator([])
        with self.assertRaises(ValueError):
            coord.execute_transaction("tx-empty")

    def test_invalid_tx_id_raises_value_error(self):
        p = Participant("db")
        coord = TwoPhaseCoordinator([p])
        with self.assertRaises(ValueError):
            coord.execute_transaction("")
        with self.assertRaises(ValueError):
            coord.execute_transaction(None)

    def test_multi_transaction_lifecycle(self):
        p1 = Participant("db1")
        p2 = Participant("db2")
        coord = TwoPhaseCoordinator([p1, p2])

        self.assertTrue(coord.execute_transaction("tx-1"))
        self.assertEqual(p1.state, ParticipantState.COMMITTED)

        # Subsequent transaction fails
        p2.should_fail_prepare = True
        self.assertFalse(coord.execute_transaction("tx-2"))
        self.assertEqual(p1.state, ParticipantState.ABORTED)
        self.assertEqual(p2.state, ParticipantState.ABORTED)
