# JM proxy conversion trial

This change is stacked on #146. It does not change the Stage transport,
original upload consent, or rendering. A valid cached proxy stays valid.

For a controlled cold A/B, use the same original, the same FFmpeg build and
isolated Companion homes. Run one conversion at a time and capture the reported
conversion time, proxy bytes, local read and transfer times. Re-importing the
same file into a warm cache is a separate test.

Start the candidate Companion for the B run with
`MONTARA_PROXY_INTEL_CPU_FIRST=1` in its environment. Without that flag, the
existing encoder preference remains. The trial only changes the first attempt
for upright, flat 1920×1080 H.264 SDR sources, 24–30 fps and at least ten
minutes long, on Intel macOS. It uses the software encoder already shipped
as the fallback in #146, verifies the result against samples from the
original, and can still retry with VideoToolbox. Remove the flag and restart
the trial process to return to the existing preference.

A separate optimization selects the retained frames before scaling, rotating
or tonemapping when the source frame rate is at least 1.5 times the output
rate. The target frame rate, geometry, projection metadata and audio settings
do not change. Test ordinary footage and a high-rate 360 source separately.
The CPU preference flag never applies to 360 or HDR media.

Before rollout, verify playback, sync and frame selection in Stage with both
proxies, including 360 viewpoints and original-quality native export. Test on
JM only, using a fresh test project and the supported Companion installer
after approval. Keep the previous Companion build available for rollback.
