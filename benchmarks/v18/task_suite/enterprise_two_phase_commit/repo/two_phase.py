class ParticipantState:
    INIT = "INIT"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"

class Participant:
    def __init__(self, name, should_fail_prepare=False):
        self.name = name
        self.should_fail_prepare = should_fail_prepare
        self.state = ParticipantState.INIT
        self.active_tx = None

    def prepare(self, tx_id):
        if not self.should_fail_prepare:
            self.state = ParticipantState.PREPARED
            self.active_tx = tx_id
            return True
        self.state = ParticipantState.ABORTED
        return False

    def commit(self, tx_id):
        self.state = ParticipantState.COMMITTED
        self.active_tx = None

    def abort(self, tx_id):
        self.state = ParticipantState.ABORTED
        self.active_tx = None

class TwoPhaseCoordinator:
    def __init__(self, participants=None):
        self.participants = list(participants or [])
        self.transaction_logs = {}

    def add_participant(self, participant):
        self.participants.append(participant)

    def execute_transaction(self, tx_id):
        # Buggy implementation:
        # If any participant votes False, coordinator returns False immediately
        # WITHOUT sending abort to the participants that already prepared!
        votes = {}
        for p in self.participants:
            vote = p.prepare(tx_id)
            votes[p.name] = vote
            if not vote:
                # Bug: leaves earlier prepared participants in PREPARED state!
                self.transaction_logs[tx_id] = "ABORTED"
                return False

        for p in self.participants:
            p.commit(tx_id)
        self.transaction_logs[tx_id] = "COMMITTED"
        return True
