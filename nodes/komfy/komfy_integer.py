"""
Komfy_Integer Node
Provides an INT value with wide constraints for flexible configuration.
"""


class KomfyInteger:
    """
    Integer input node for Komfy protocol.
    Provides a simple INT value passthrough with wide constraints.
    Label is taken from the node title in the workflow.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 1024,
                    "min": -2147483648,  # -2^31
                    "max": 2147483647,   # 2^31 - 1
                    "step": 1,
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "execute"
    CATEGORY = "HMT Suite/Komfy"

    def execute(self, value):
        """Simple passthrough of the integer value"""
        return (value,)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Always re-execute to ensure updates propagate"""
        return float("nan")


# Node registration
NODE_CLASS_MAPPINGS = {
    "Komfy_Integer": KomfyInteger
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Komfy_Integer": "Integer"
}
