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
        if not name or not callable(action) or not callable(compensate):
            raise ValueError("Step name and callables required")
        if any(s["name"] == name for s in self.steps):
            raise ValueError("Duplicate step name")
        self.steps.append({"name": name, "action": action, "compensate": compensate})

    def execute(self, context):
        completed_steps = []
        results = {}

        for step in self.steps:
            name = step["name"]
            try:
                out = step["action"](context)
                results[name] = out
                completed_steps.append(step)
            except Exception as exc:
                # Rollback completed steps in reverse order
                compensated_names = []
                for comp_step in reversed(completed_steps):
                    comp_step["compensate"](context)
                    compensated_names.append(comp_step["name"])

                self.execution_log.append({
                    "status": "failed",
                    "failed_step": name,
                    "compensated": compensated_names,
                    "error": str(exc),
                })
                raise SagaExecutionError(name, exc, compensated_names) from exc

        self.execution_log.append({
            "status": "completed",
            "results": results,
        })
        return {"success": True, "results": results}
