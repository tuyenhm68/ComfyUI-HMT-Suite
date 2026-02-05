# Komfy Protocol Nodes

Data-centric input nodes for zero-config app generation.

**Version:** 1.2.0
**Category:** `HMT Suite/Komfy`

---

## Nodes

### 1. Komfy_Integer
- **Output:** `INT`
- **Range:** -2,147,483,648 to 2,147,483,647
- **Default:** 1024
- **UI:** Slider (auto-inferred from min/max)

### 2. Komfy_Float
- **Output:** `FLOAT`
- **Range:** -999,999.0 to 999,999.0
- **Default:** 1.0
- **Step:** 0.01
- **UI:** Slider (auto-inferred from min/max)

### 3. Komfy_String
- **Output:** `STRING`
- **Multiline:** Yes (Text Area)
- **Default:** Empty string

### 4. Komfy_Boolean
- **Output:** `BOOLEAN`
- **Default:** True
- **UI:** Switch/Checkbox

### 5. Komfy_AspectRatio
- **Output:** `INT`, `INT` (width, height)
- **Ratios:** 1:1, 4:3, 3:4, 16:9, 9:16, 21:9, 3:2, 2:3, 5:4, 4:5
- **Resolutions:** Multiple predefined resolutions for each ratio
- **UI:** Dropdown (auto-inferred from options list)

---

## Usage

1. Add a Komfy node to your workflow (e.g., `Komfy_Integer`)
2. **Rename the node** to set its label (e.g., "Image Width")
3. Set the value in the node widget
4. Connect the output to any compatible input
5. Save workflow

The App Builder will automatically:
- Use the **node title** as the UI label
- Infer the **control type** from constraints (slider, input, textarea, switch)
- Generate the appropriate UI component

---

## Example Workflow

### Basic inputs:
```
┌─────────────────┐
│ Komfy_Integer   │ (renamed to "Width")
│ value: 512      │ ──► Empty Latent Image (width)
└─────────────────┘

┌─────────────────┐
│ Komfy_Float     │ (renamed to "CFG Scale")
│ value: 7.5      │ ──► KSampler (cfg)
└─────────────────┘

┌─────────────────┐
│ Komfy_String    │ (renamed to "Positive Prompt")
│ value: "..."    │ ──► CLIP Text Encode (text)
└─────────────────┘
```

### Aspect Ratio workflow:
```
┌──────────────────────────┐
│ Komfy_AspectRatio        │ (renamed to "Image Size")
│ ratio: "16:9 (1920x1080)"│
│                          │
│  ├─ width (1920) ────────┼──► Empty Latent Image (width)
│  └─ height (1080) ───────┼──► Empty Latent Image (height)
└──────────────────────────┘
```

---

## Troubleshooting

### Nodes not appearing in ComfyUI?

1. **Restart ComfyUI completely** (stop and start the server)
2. Check ComfyUI console for any import errors
3. Run test script:
   ```bash
   cd ComfyUI/custom_nodes/ComfyUI-HMT-Suite
   python test_komfy_nodes.py
   ```
4. Clear Python cache:
   ```bash
   find . -type d -name __pycache__ -exec rm -rf {} +
   ```
5. Check that `nodes/komfy/__init__.py` exists and is valid

### Nodes appear but don't work?

1. Check that you've renamed the node to set a proper label
2. Verify the output is connected to a compatible input type
3. Check ComfyUI console for execution errors

---

## Technical Details

- **Simple passthrough**: Nodes directly return the input value
- **No custom logic**: Minimal overhead
- **Always re-execute**: `IS_CHANGED` returns `NaN` to force updates
- **ComfyUI-native**: Uses standard ComfyUI widget types
