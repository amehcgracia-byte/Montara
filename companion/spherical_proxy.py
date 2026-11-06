"""Keep a reduced panorama discoverable as 360 without another video encode."""
from pathlib import Path


def preserve_panorama(path: Path, probe) -> None:
    # Same Apache-2.0 Google injector vendored by the pinned Editor. Kept local
    # so proxy creation works without installing the optional video renderer.
    from spatialmedia import metadata_utils

    tagged = path.with_name(path.stem + ".spherical.mp4")
    messages = []
    try:
        metadata = metadata_utils.Metadata(projection="equirectangular", stereo_mode="mono")
        metadata.video = metadata_utils.generate_spherical_xml(projection="equirectangular", stereo=None)
        metadata_utils.inject_metadata(str(path), str(tagged), metadata, messages.append)
        if any("error" in str(message).lower() for message in messages):
            raise RuntimeError("Could not preserve 360 projection metadata")
        stream = next(s for s in probe(tagged).get("streams", []) if s.get("codec_type") == "video")
        spherical = any("spherical" in str(d.get("side_data_type", "")).lower()
                        for d in stream.get("side_data_list", []))
        if not spherical or stream["width"] != 2 * stream["height"]:
            raise RuntimeError("The small panorama did not retain its 360 projection")
        tagged.replace(path)
    finally:
        tagged.unlink(missing_ok=True)
