class SagaExecutionError(RuntimeError):
    def __init__(self, step, original_error, compensated_steps):
        super().__init__(f"Saga failed at step '{step}': {original_error}")
        self.failed_step = step
        self.original_error = original_error
        self.compensated_steps = compensated_steps

class SagaCoordinator:
    def __init__(self):
        self.steps = []
        self.execution_log = []

    def add_step(self, name, action, compensate):
        self.steps.append({"name": name, "action": action, "compensate": compensate})

    def execute(self, context):
        # Buggy implementation: runs steps but does NOT execute compensation on failure
        results = {}
        for step in self.steps:
            results[step["name"]] = step["action"](context)
        return {"success": True, "results": results}
