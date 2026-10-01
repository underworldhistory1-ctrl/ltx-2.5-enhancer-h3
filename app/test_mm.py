import sys
sys.path.append("/root/ltx-enhancer/comfy_backend")
import comfy.model_management as mm

print("VRAM Total:", mm.get_total_memory(mm.get_torch_device()) / 1e9, "GB")
print("VRAM Free:", mm.get_free_memory(mm.get_torch_device()) / 1e9, "GB")
