class AgentCardNotFound(RuntimeError):
    pass


class AgentSessionMismatch(RuntimeError):
    pass


class AgentLLMError(RuntimeError):
    pass


class AgentToolError(RuntimeError):
    pass
