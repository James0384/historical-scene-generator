# Historical Scene Generator

Blender add-on for procedural historical environments + synthetic training data (RGB + depth maps). Built to support multimodal AI training pipelines — like those for Grok at xAI.

**Why this project?**  
Professional 3D modeler (Star Spangled Adventures — 39 episodes shipped). This tool demonstrates Python/Blender scripting + procedural generation for scalable labeled 3D data. Applied to xAI's AI Tutor - 3D Specialist role (Feb 2026).

**Features (v1.7 MVP)**
- Sidebar panel (View3D > Historical Synth) with eyedropper selectors for building/tree meshes, fence material, camera
- Batch generation: clear scene → add ground → procedural fence (posts + rails) → scaled/positioned building → randomized trees (with fence buffer & ground bounds)
- Camera setup (user or default orbiting)
- Fast Eevee render → RGB PNG + normalized depth EXR per scene
- Compositor auto-setup for clean passes
- Output to custom folder (default: //training_data/)

**Setup**
1. Blender 4.2+ (tested 4.5)
2. **Recommended**: Place script in folder `historical_scene_generator/` as `__init__.py` → zip folder → Edit > Preferences > Add-ons > Install > enable "Historical Scene Generator"
3. **Quick test**: Paste `generate_scenes.py` into Text Editor > Run Script
4. Select source building/tree meshes + fence material in panel
5. Set batch size & output folder
6. Hit "Generate Batch Scenes"

**Development note**  
Built in a 30-day accelerated Python + Blender sprint, using Grok (xAI) as a collaborative coding partner to prototype fast. I defined requirements from production experience (historical accuracy, procedural envs, synthetic data needs), guided iterations, tested outputs, and refined for reliability. This mirrors how I'd contribute to xAI's 3D pipelines — leveraging best tools for speed + quality.

**Next steps**  
- Style/seed params (colonial, victorian, etc.)
- Multi-class segmentation (object index / crypto passes)
- Camera animation loops
- 1000+ scene batching + automation

Made by James Miller (@JamesMiller_X)  
ArtStation: https://www.artstation.com/james03843  
Applied to xAI 3D Tutor role — excited to scale this kind of work!

Star Spangled Adventures creds: https://www.imdb.com/name/nm14167507/
