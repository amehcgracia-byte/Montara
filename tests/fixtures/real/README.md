# Real test material (private — do not copy to public repos)

Low-resolution excerpts from a ZuckerZauber Session (27.07.26, "Ambient extorsion")
and a talking-head clip, used by `tests/e2e_journey.py`. Pixelated on purpose.

| File          | Source                                              | Excerpt                      |
|---------------|-----------------------------------------------------|------------------------------|
| master.mp3    | edited/sound/ZZ24.7 06 Ambient extorsion .mp3       | 300–390 s of the master      |
| cam-fixed.mp4 | raw/video/ZZ24.7 01.mov (fixed rear camera)         | 170–275 s, 640x360 25 fps    |
| cam-360.mp4   | raw/video/insta360/VID_20260727_213248_00_030.mp4   | 385–490 s, 640x320 equirect  |
| talk.mp4      | Show C0271 - corte limpio sin efectos.mp4           | first 90 s, 640x360          |

Measured sync (onset correlation, four 60 s windows agree within 10 ms):
camera time = master time − 122.33 s (fixed) and + 92.29 s (360). In these excerpts
the master starts 7.67 s into cam-fixed and 7.29 s into cam-360, so Stage has to
find a real offset, not zero.
