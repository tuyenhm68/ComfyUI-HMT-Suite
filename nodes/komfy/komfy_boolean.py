"""
Komfy_Boolean Node
Provides a BOOLEAN value (True/False).
"""


class KomfyBoolean:
    """
    Boolean input node for Komfy protocol.
    Provides a simple BOOLEAN value passthrough.
    Label is taken from the node title in the workflow.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("BOOLEAN", {
                    "default": True,
                }),
            }
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("value",)
    FUNCTION = "execute"
    CATEGORY = "HMT Suite/Komfy"

    def execute(self, value):
        """Simple passthrough of the boolean value"""
        return (value,)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Always re-execute to ensure updates propagate"""
        return float("nan")


# Node registration
NODE_CLASS_MAPPINGS = {
    "Komfy_Boolean": KomfyBoolean
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Komfy_Boolean": "Boolean"
}
