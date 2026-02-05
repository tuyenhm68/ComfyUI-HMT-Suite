"""
Komfy_Float Node
Provides a FLOAT value with wide constraints for flexible configuration.
"""


class KomfyFloat:
    """
    Float input node for Komfy protocol.
    Provides a simple FLOAT value passthrough with wide constraints.
    Label is taken from the node title in the workflow.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("FLOAT", {
                    "default": 1.0,
                    "min": -999999.0,
                    "max": 999999.0,
                    "step": 0.01,
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("FLOAT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "execute"
    CATEGORY = "HMT Suite/Komfy"

    def execute(self, value):
        """Simple passthrough of the float value"""
        return (value,)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Always re-execute to ensure updates propagate"""
        return float("nan")


# Node registration
NODE_CLASS_MAPPINGS = {
    "Komfy_Float": KomfyFloat
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Komfy_Float": "Float"
}
