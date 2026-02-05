"""
Komfy_AspectRatio Node
Provides aspect ratio selection with automatic width/height calculation.
"""


class KomfyAspectRatio:
    """
    Aspect ratio selector node for Komfy protocol.
    Provides width and height outputs based on selected ratio.
    Label is taken from the node title in the workflow.
    """

    # Predefined aspect ratios with their resolutions
    # Format: "ratio_name": (width, height)
    ASPECT_RATIOS = {
        "1:1 (Square - 1024x1024)": (1024, 1024),
        "1:1 (Square - 512x512)": (512, 512),
        "4:3 (Landscape - 1024x768)": (1024, 768),
        "3:4 (Portrait - 768x1024)": (768, 1024),
        "16:9 (Landscape - 1920x1080)": (1920, 1080),
        "16:9 (Landscape - 1280x720)": (1280, 720),
        "16:9 (Landscape - 1024x576)": (1024, 576),
        "9:16 (Portrait - 1080x1920)": (1080, 1920),
        "9:16 (Portrait - 720x1280)": (720, 1280),
        "9:16 (Portrait - 576x1024)": (576, 1024),
        "21:9 (Ultrawide - 2560x1080)": (2560, 1080),
        "21:9 (Ultrawide - 1920x823)": (1920, 823),
        "3:2 (Landscape - 1536x1024)": (1536, 1024),
        "2:3 (Portrait - 1024x1536)": (1024, 1536),
        "5:4 (Landscape - 1280x1024)": (1280, 1024),
        "4:5 (Portrait - 1024x1280)": (1024, 1280),
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ratio": (list(cls.ASPECT_RATIOS.keys()), {
                    "default": "1:1 (Square - 1024x1024)"
                }),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "execute"
    CATEGORY = "HMT Suite/Komfy"

    def execute(self, ratio):
        """Return width and height for selected aspect ratio"""
        width, height = self.ASPECT_RATIOS[ratio]
        return (width, height)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Always re-execute to ensure updates propagate"""
        return float("nan")


# Node registration
NODE_CLASS_MAPPINGS = {
    "Komfy_AspectRatio": KomfyAspectRatio
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Komfy_AspectRatio": "Aspect Ratio"
}
