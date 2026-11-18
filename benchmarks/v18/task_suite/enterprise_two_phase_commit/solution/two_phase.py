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
        if not tx_id or not isinstance(tx_id, str):
            raise ValueError("tx_id must be non-empty string")
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
        if not tx_id or not isinstance(tx_id, str):
            raise ValueError("tx_id must be non-empty string")
        if not self.participants:
            raise ValueError("No participants registered")

        prepared_participants = []
        all_prepared = True

        for p in self.participants:
            try:
                vote = p.prepare(tx_id)
                if vote:
                    prepared_participants.append(p)
                else:
                    all_prepared = False
                    break
            except Exception:
                all_prepared = False
                break

        if not all_prepared:
            # Abort all participants that entered PREPARED state
            for p in self.participants:
                try:
                    p.abort(tx_id)
                except Exception:
                    pass
            self.transaction_logs[tx_id] = "ABORTED"
            return False

        # Phase 2: Commit all
        for p in self.participants:
            p.commit(tx_id)
        self.transaction_logs[tx_id] = "COMMITTED"
        return True
