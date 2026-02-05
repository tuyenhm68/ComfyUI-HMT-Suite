"""
Komfy_String Node
Provides a STRING value with multiline support.
"""


class KomfyString:
    """
    String input node for Komfy protocol.
    Provides a simple STRING value passthrough with multiline support.
    Label is taken from the node title in the workflow.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("STRING", {
                    "default": "",
                    "multiline": True,  # Enables text area for longer text
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)
    FUNCTION = "execute"
    CATEGORY = "HMT Suite/Komfy"

    def execute(self, value):
        """Simple passthrough of the string value"""
        return (value,)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Always re-execute to ensure updates propagate"""
        return float("nan")


# Node registration
NODE_CLASS_MAPPINGS = {
    "Komfy_String": KomfyString
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Komfy_String": "String"
}
