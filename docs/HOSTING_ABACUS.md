# Abacus: preliminary hosting assessment (2026-10-25)

This is research only. No subscription was purchased and Montara was not migrated.

The current Cloud product page lists a separate USD 10/month Ubuntu machine, first month free, 2 vCPU, 8 GB RAM and 50 GB persistent disk, public URL and SSH. It explicitly includes no Abacus AI credits. It is a plausible small CPU-based beta host for Montara's Python/FFmpeg stack, subject to a real installation and timed render test. The stated plan does not advertise a GPU. Start with one processing job at a time; do not promise 50 concurrent render jobs or unlimited storage.

Source: https://cloud.abacus.ai/

The SuperComputer marketing page advertises USD 10, while the detailed ChatLLM billing documentation says SuperComputer requires Pro (USD 20/month total) and costs 1 credit per 5 active minutes; agent usage is billed separately. At continuous uptime that is 8,640 credits per 30-day month before model, image or video work. Confirm the actual product and checkout terms before buying.

Sources: https://supercomputer.abacus.ai/ and https://abacus.ai/help/chatllm-ai-super-assistant/faqs/billing

Personal access to multiple chat/image/video models must not be treated as an unlimited production inference API for Montara's customers. Hosting, video rendering, source-file storage and inference need separate measured budgets. The current Vercel review gallery can stay where it is while evaluating a backend host.
