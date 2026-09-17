class ContractError(RuntimeError):
    """Base error for locked-contract validation failures."""

class ManifestValidationError(ContractError):
    pass

class ContractHashMismatch(ContractError):
    pass
