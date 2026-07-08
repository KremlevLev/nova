# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "onnxruntime>=1.20", "numpy", "soundfile", "librosa", "transformers",
#   "numba>=0.60.0", "llvmlite>=0.43.0",
# ]
# ///
# numba/llvmlite pinned: librosa otherwise pulls numba 0.53.1 → llvmlite 0.36,
# which fails to build on Python 3.12.
"""Run the exported Qwen3-TTS ONNX sub-parts (build blocks + full text→speech).
One --model-path points at  onnx/{device}_{precision}/  (flat, manifest-driven):
  text_embed.onnx      text_ids[B,T]            → text_embeds[B,T,2048]   (text_projection∘text_embedding)
  codec_embed.onnx     codec_ids[B,T]           → codec_embeds[B,T,2048]  (talker first-codebook embed)
  talker.onnx          inputs_embeds[B,T,2048] + position_ids[3,B,T] + mask → (logits[B,T,V], hidden[B,T,2048])
  code_predictor.onnx  talker_hidden[B,2048] + codec_ids[B,16] → group_logits[B,15,vocab]  (causal teacher-forced)
  residual_embed.onnx  codec_ids[B,16]          → step_embed[B,2048]      (codec_hiddens.sum — next talker input)
  tok_encoder.onnx     audio[B,1,24000]         → codes[B,frames,16]
  tok_decoder.onnx     codes[B,25,16]           → waveform[B,1,L]   (FIXED 25 frames)
GENERATION (`generate`) mirrors `Qwen3TTSForConditionalGeneration.generate` with
`non_streaming_mode=True` for the two convertible checkpoints:
  • text-to-speech  — text + language
  • voice design    — text + instruct (natural-language style)            [VoiceDesign]
  • custom voice    — text + speaker name (+ optional instruct)           [CustomVoice]
ICL audio-clone (ref_audio/ref_text) is a `base`-model feature (needs the speaker
encoder, which is absent here) and is intentionally not implemented.
The talker is a no-cache forward, so the AR loop re-runs the growing prefix each
step (correct, O(n²)). MROPE reduces to arange here (`get_rope_index` =
cumsum(mask)-1, 3 identical rows for an unpadded single sequence).
Usage:
  uv run inference.py --model-path onnx/cpu_fp32 --selftest
  uv run inference.py --model-path onnx/cpu_fp32 --tts-dir voicedesign \
      --text "Hello there." --instruct "A calm, low female voice." --out out.wav
  uv run inference.py --model-path onnx/cpu_fp32 --tts-dir customvoice \
      --text "你好。" --speaker ethan --language chinese --out out.wav
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

SR = 24000
DEC_FRAMES = 25            # tok_decoder is exported at a fixed 25-frame length
N_GROUPS = 16


def cosine(a, b):
    a, b = a.ravel().astype(np.float64), b.ravel().astype(np.float64)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# ── sampling helpers (numpy; mirror HF generate logic) ──────────────────────────
def _apply_repetition_penalty(logits, prev_ids, penalty):
    if penalty == 1.0 or not prev_ids:
        return logits
    idx = np.array(sorted(set(int(i) for i in prev_ids)), dtype=np.int64)
    sc = logits[idx]
    logits[idx] = np.where(sc < 0, sc * penalty, sc / penalty)
    return logits


def _sample(logits, do_sample, top_k, top_p, temperature, rng):
    logits = logits.astype(np.float64)
    if not do_sample or temperature <= 0:
        return int(np.argmax(logits))
    logits = logits / max(temperature, 1e-6)
    if top_k and top_k > 0:
        k = min(top_k, logits.shape[-1])
        kth = np.partition(logits, -k)[-k]
        logits = np.where(logits < kth, -np.inf, logits)
    logits -= logits.max()
    probs = np.exp(logits)
    probs /= probs.sum()
    if top_p and top_p < 1.0:
        order = np.argsort(probs)[::-1]
        csum = np.cumsum(probs[order])
        cut = np.searchsorted(csum, top_p) + 1
        keep = order[:cut]
        mask = np.zeros_like(probs)
        mask[keep] = probs[keep]
        probs = mask / mask.sum()
    return int(rng.choice(len(probs), p=probs))


class Pipeline:
    """Manifest-driven loader for the exported Qwen3-TTS ONNX sub-parts."""

    def __init__(self, model_path: str, tts_dir: str = None):
        import onnxruntime as ort

        self.root = Path(model_path)
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        sm = self.manifest["sub_models"]
        prov = self.manifest.get("execution_provider", "CPUExecutionProvider")
        avail = ort.get_available_providers()
        if prov not in avail:
            print(f"  [warn] manifest EP {prov} unavailable; falling back to CPU", file=sys.stderr)
            prov = "CPUExecutionProvider"
        self.provider = prov

        so = ort.SessionOptions()
        so.log_severity_level = 3

        def sess(name):
            if name not in sm:
                return None
            return ort.InferenceSession(str(self.root / sm[name]["filename"]),
                                        so, providers=[prov])

        self.text_embed = sess("text_embed")
        self.codec_embed = sess("codec_embed")
        self.talker = sess("talker")
        self.code_predictor = sess("code_predictor")
        self.residual_embed = sess("residual_embed")
        self.tok_encoder = sess("tok_encoder")
        self.tok_decoder = sess("tok_decoder")
        self.speaker_encoder = sess("speaker_encoder")   # Base only (voice-clone x-vector)
        self.talker_cache = sess("talker_cache")         # optional O(n) KV-cache talker
        if self.talker_cache is not None:                # ordered past-input names (flattened)
            self._past_names = [i.name for i in self.talker_cache.get_inputs()][3:]

        # config + tokenizer (only needed for full generation)
        self.tts_dir = tts_dir
        self._cfg = None
        self._tok = None
        if tts_dir is not None:
            self._cfg = json.loads((Path(tts_dir) / "config.json").read_text())

    # ── building blocks (each verified against PyTorch in eval_*.py) ──────────
    def embed_text(self, text_ids):                 # [B,T] int64 → [B,T,2048]
        return self.text_embed.run(None, {"text_ids": np.asarray(text_ids, np.int64)})[0]

    def embed_codec(self, codec_ids):               # [B,T] int64 → [B,T,2048]
        return self.codec_embed.run(None, {"codec_ids": np.asarray(codec_ids, np.int64)})[0]

    def talker_step(self, inputs_embeds, position_ids, attention_mask):
        """→ (logits[B,T,V], hidden[B,T,2048]).  Talker emits both since the
        code_predictor is conditioned on the talker's last hidden state."""
        return self.talker.run(None, {
            "inputs_embeds": inputs_embeds.astype(np.float32),
            "position_ids": np.asarray(position_ids, np.int64),
            "attention_mask": np.asarray(attention_mask, np.int64)})

    def talker_cache_step(self, inputs_embeds, position_ids, attention_mask, past):
        """KV-cache talker: → (logits[B,cur,V], hidden[B,cur,2048], present[list of 56]).
        `past`/`present` are ordered lists of the flattened K/V tensors (layer0_k, layer0_v,
        layer1_k, …). Empty past = prefill; len-1 cur = decode."""
        feed = {"inputs_embeds": inputs_embeds.astype(np.float32),
                "position_ids": np.asarray(position_ids, np.int64),
                "attention_mask": np.asarray(attention_mask, np.int64)}
        for name, t in zip(self._past_names, past):
            feed[name] = t.astype(np.float32)
        out = self.talker_cache.run(None, feed)
        return out[0], out[1], list(out[2:])      # logits, hidden, present

    def predict_residual(self, talker_hidden, codec_ids):   # causal teacher-forced
        return self.code_predictor.run(None, {
            "talker_hidden": talker_hidden.astype(np.float32),
            "codec_ids": np.asarray(codec_ids, np.int64)})[0]

    def step_embed(self, codec_ids):                # [B,16] → [B,2048]  (sum of group embeds)
        return self.residual_embed.run(None, {"codec_ids": np.asarray(codec_ids, np.int64)})[0]

    @staticmethod
    def _load_ref_wav(path):
        """Load a reference wav → mono float32 @ 24 kHz."""
        import soundfile as sf
        wav, sr = sf.read(path, dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        if sr != SR:
            import librosa
            wav = librosa.resample(wav, orig_sr=sr, target_sr=SR)
        return wav.astype(np.float32)

    def encode_chunked(self, wav):                  # wav [L] 24k → ref codes [T,16]
        """tok_encoder is fixed at 1 s (24000 samples); encode in 1 s windows + concat."""
        out = []
        for s in range(0, max(len(wav), 1), SR):
            c = wav[s:s + SR]
            if len(c) < SR:
                c = np.pad(c, (0, SR - len(c)))
            out.append(self.encode(c.reshape(1, 1, SR).astype(np.float32))[0])  # [frames,16]
        return np.concatenate(out, axis=0).astype(np.int64)

    def encode(self, audio):                        # [B,1,24000] → [B,frames,16]
        return self.tok_encoder.run(None, {"audio": audio.astype(np.float32)})[0]

    def decode(self, codes):                        # [B,F,16] → [B,1,L]
        return self.tok_decoder.run(None, {"audio_codes": np.asarray(codes, np.int64)})[0]

    def decode_chunked(self, codes):
        """Decode arbitrary-length codes through the fixed-25-frame decoder by
        tiling each 25-frame chunk; tail is padded by repetition then trimmed."""
        F = codes.shape[1]
        outs = []
        for s in range(0, F, DEC_FRAMES):
            chunk = codes[:, s:s + DEC_FRAMES]
            if chunk.shape[1] < DEC_FRAMES:                     # pad tail by repeat
                idx = np.arange(DEC_FRAMES) % chunk.shape[1]
                chunk = chunk[:, idx]
                wav = self.decode(chunk)
                keep = int(round(wav.shape[-1] * (F - s) / DEC_FRAMES))
                outs.append(wav[..., :keep]); break
            outs.append(self.decode(chunk))
        return np.concatenate(outs, axis=-1)

    # ── config / tokenizer accessors ──────────────────────────────────────────
    @property
    def cfg(self):
        if self._cfg is None:
            raise RuntimeError("Pass --tts-dir (the HF model dir) for generation: "
                               "config token ids + tokenizer live there.")
        return self._cfg

    @property
    def model_type(self):
        """tts_model_type from config: 'voice_design' | 'custom_voice' | 'base'.
        Each model exposes different features (see _check_features)."""
        c = self.cfg
        return (c.get("tts_model_type")
                or c.get("talker_config", {}).get("tts_model_type") or "unknown")

    def _check_features(self, instruct=None, speaker=None, ref_audio=None):
        """Gate features by model type so a flag that the loaded model can't honor
        fails loudly instead of silently doing nothing:
          voice_design → instruct (natural-language style); no speaker/ref
          custom_voice → speaker (built-in voices) + optional instruct; no ref
          base         → voice cloning (ref_audio/ref_text); no speaker/instruct
        """
        mt = self.model_type
        if speaker and mt != "custom_voice":
            raise ValueError(f"--speaker is a CustomVoice feature, but this model is '{mt}'. "
                             "Use a customvoice checkpoint, or drop --speaker.")
        if instruct and mt not in ("voice_design", "custom_voice"):
            raise ValueError(f"--instruct is a VoiceDesign/CustomVoice feature, but this model "
                             f"is '{mt}'. Drop --instruct (Base clones from --ref-audio instead).")
        if ref_audio and mt != "base":
            raise ValueError(f"voice cloning (--ref-audio) is a Base-model feature, but this "
                             f"model is '{mt}'. Use a base checkpoint.")
        if mt == "custom_voice" and not speaker:
            print("  [note] CustomVoice with no --speaker → model's default voice.",
                  file=sys.stderr)

    @property
    def tokenizer(self):
        if self._tok is None:
            from transformers import AutoTokenizer
            self._tok = AutoTokenizer.from_pretrained(self.tts_dir, trust_remote_code=True)
        return self._tok

    def _ids(self, text):
        enc = self.tokenizer(text, return_tensors="np")
        ids = enc["input_ids"]
        return ids if ids.ndim == 2 else ids[None]

    # ── full text→speech generation ────────────────────────────────────────────
    def generate(self, text, language="Auto", instruct=None, speaker=None,
                 ref_audio=None, ref_text=None,
                 max_new_tokens=2048, do_sample=True, top_k=50, top_p=1.0,
                 temperature=0.9, repetition_penalty=1.05,
                 sub_do_sample=True, sub_top_k=50, sub_top_p=1.0, sub_temperature=0.9,
                 seed=0, verbose=True):
        """Mirror Qwen3TTSForConditionalGeneration.generate (non_streaming_mode=True).
        Features are gated by model type (voice_design=instruct, custom_voice=speaker,
        base=clone). Returns codes [T,16] (int64). Decode with `decode_chunked(codes[None])`.
        """
        cfg = self.cfg
        self._check_features(instruct=instruct, speaker=speaker, ref_audio=ref_audio)
        if ref_audio:
            return self._generate_clone(text, ref_audio, ref_text, language=language,
                                        max_new_tokens=max_new_tokens, do_sample=do_sample,
                                        top_k=top_k, top_p=top_p, temperature=temperature,
                                        repetition_penalty=repetition_penalty,
                                        sub_do_sample=sub_do_sample, sub_top_k=sub_top_k,
                                        sub_top_p=sub_top_p, sub_temperature=sub_temperature,
                                        seed=seed, verbose=verbose)
        tc = cfg["talker_config"]
        H = tc["hidden_size"]
        rng = np.random.default_rng(seed)

        # token ids
        tts_bos, tts_eos, tts_pad = (cfg["tts_bos_token_id"], cfg["tts_eos_token_id"],
                                     cfg["tts_pad_token_id"])
        codec_eos = tc["codec_eos_token_id"]
        codec_pad, codec_bos = tc["codec_pad_id"], tc["codec_bos_id"]
        vocab = tc["vocab_size"]

        # 0) text → ids (assistant template).  role = first 3, trailing = last 5.
        assistant = f"<|im_start|>assistant\n{text}<|im_end|>\n<|im_start|>assistant\n"
        input_id = self._ids(assistant)                       # [1, L]
        if input_id.shape[1] < 9:
            raise ValueError("text tokenized too short for the assistant template")

        # 1) special text embeds (tts_bos/eos/pad)
        spec = self.embed_text([[tts_bos, tts_eos, tts_pad]])   # [1,3,H]
        bos_e, eos_e, pad_e = spec[:, 0:1], spec[:, 1:2], spec[:, 2:3]

        # 2) language + codec prefill tags
        lang = (language or "auto").lower()
        if lang == "auto" or lang not in tc.get("codec_language_id", {}):
            language_id = None
        else:
            language_id = tc["codec_language_id"][lang]
        if language_id is None:
            codec_prefill = [[tc["codec_nothink_id"], tc["codec_think_bos_id"],
                              tc["codec_think_eos_id"]]]
        else:
            codec_prefill = [[tc["codec_think_id"], tc["codec_think_bos_id"],
                              language_id, tc["codec_think_eos_id"]]]
        codec0 = self.embed_codec(codec_prefill)                # [1,P,H]
        codec1 = self.embed_codec([[codec_pad, codec_bos]])     # [1,2,H]

        # speaker (custom voice): speaker name → spk_id → codec table embed
        speaker_embed = None
        if speaker:
            spk_map = tc.get("spk_id", {})
            if speaker.lower() not in spk_map:
                raise ValueError(f"Speaker '{speaker}' not in spk_id {list(spk_map)[:8]}…")
            speaker_embed = self.embed_codec([[spk_map[speaker.lower()]]])   # [1,1,H]

        if speaker_embed is None:
            codec_input = np.concatenate([codec0, codec1], axis=1)
        else:
            codec_input = np.concatenate([codec0, speaker_embed, codec1], axis=1)

        # 3) instruct prefix (voice design) — prepended text_projection embeds
        prefix = []
        if instruct:
            instruct_text = f"<|im_start|>user\n{instruct}<|im_end|>\n"
            prefix.append(self.embed_text(self._ids(instruct_text)))

        # 4) assemble talker prefill (non_streaming_mode=True)
        role = self.embed_text(input_id[:, :3])                 # <|im_start|>assistant\n
        pad_block = np.concatenate(
            [np.repeat(pad_e, codec_input.shape[1] - 2, axis=1), bos_e], axis=1)
        talker_in = np.concatenate([role, pad_block + codec_input[:, :-1]], axis=1)

        body_ids = input_id[:, 3:-5]                            # pure text tokens
        Ltext = body_ids.shape[1]
        text_body = self.embed_text(body_ids)                   # [1,Ltext,H]
        block1 = (np.concatenate([text_body, eos_e], axis=1)
                  + self.embed_codec([[codec_pad] * (Ltext + 1)]))
        block2 = pad_e + self.embed_codec([[codec_bos]])        # [1,1,H]
        talker_in = np.concatenate([talker_in, block1, block2], axis=1)
        if prefix:
            talker_in = np.concatenate(prefix + [talker_in], axis=1)
        # trailing_text_hidden is just tts_pad in non_streaming mode → add pad_e each step
        trailing = pad_e[:, 0]                                  # [1,H]

        return self._ar_loop(talker_in, trailing, vocab, codec_eos, max_new_tokens,
                             do_sample, top_k, top_p, temperature, repetition_penalty,
                             sub_do_sample, sub_top_k, sub_top_p, sub_temperature, seed, verbose)

    def _ar_loop(self, talker_in, trailing, vocab, codec_eos, max_new_tokens, do_sample,
                 top_k, top_p, temperature, repetition_penalty, sub_do_sample, sub_top_k,
                 sub_top_p, sub_temperature, seed, verbose):
        """AR talker loop (MROPE→arange). Uses the O(n) KV-cache talker if exported,
        else the no-cache O(n²) talker. Shared by all generation paths. Returns codes [T,16]."""
        if self.talker_cache is not None:
            return self._ar_loop_cached(talker_in, trailing, vocab, codec_eos, max_new_tokens,
                                        do_sample, top_k, top_p, temperature, repetition_penalty,
                                        sub_do_sample, sub_top_k, sub_top_p, sub_temperature,
                                        seed, verbose)
        if self.talker is None:
            raise RuntimeError("no talker model found: need talker_cache.onnx (preferred) or "
                               "talker.onnx in the model dir.")
        rng = np.random.default_rng(seed)
        suppress = np.array([i for i in range(vocab - 1024, vocab) if i != codec_eos],
                            dtype=np.int64)
        all_codes, prev_first = [], []
        for step in range(max_new_tokens):
            T = talker_in.shape[1]
            pos = np.broadcast_to(np.arange(T), (3, 1, T)).copy()
            mask = np.ones((1, T), dtype=np.int64)
            logits, hidden = self.talker_step(talker_in, pos, mask)
            first = logits[0, -1].astype(np.float64).copy()
            first[suppress] = -np.inf
            first = _apply_repetition_penalty(first, prev_first, repetition_penalty)
            code0 = _sample(first, do_sample, top_k, top_p, temperature, rng)
            if code0 == codec_eos:
                break
            prev_first.append(code0)
            th = hidden[0, -1][None].astype(np.float32)
            codes16 = np.zeros((1, N_GROUPS), dtype=np.int64)
            codes16[0, 0] = code0
            for j in range(1, N_GROUPS):
                gl = self.predict_residual(th, codes16)
                codes16[0, j] = _sample(gl[0, j - 1], sub_do_sample, sub_top_k, sub_top_p,
                                        sub_temperature, rng)
            all_codes.append(codes16[0].copy())
            nxt = self.step_embed(codes16)[:, None] + trailing[:, None]
            talker_in = np.concatenate([talker_in, nxt], axis=1)
            if verbose and (step + 1) % 25 == 0:
                print(f"    …{step + 1} frames", file=sys.stderr)
        codes = np.stack(all_codes, axis=0).astype(np.int64) if all_codes \
            else np.zeros((0, N_GROUPS), np.int64)
        if verbose:
            print(f"  generated {codes.shape[0]} frames")
        return codes

    def _ar_loop_cached(self, talker_in, trailing, vocab, codec_eos, max_new_tokens, do_sample,
                        top_k, top_p, temperature, repetition_penalty, sub_do_sample, sub_top_k,
                        sub_top_p, sub_temperature, seed, verbose):
        """O(n) KV-cache AR loop: prefill once, then decode one token/step feeding the cache.
        Numerically identical to the no-cache loop (same positions, full causal attention)."""
        rng = np.random.default_rng(seed)
        suppress = np.array([i for i in range(vocab - 1024, vocab) if i != codec_eos], dtype=np.int64)
        past = [np.zeros((1, 8, 0, 128), np.float32) for _ in self._past_names]
        T0 = talker_in.shape[1]
        pos = np.broadcast_to(np.arange(T0), (3, 1, T0)).copy()
        logits, hidden, past = self.talker_cache_step(talker_in, pos, np.ones((1, T0), np.int64), past)
        total = T0
        all_codes, prev_first = [], []
        for step in range(max_new_tokens):
            first = logits[0, -1].astype(np.float64).copy()
            first[suppress] = -np.inf
            first = _apply_repetition_penalty(first, prev_first, repetition_penalty)
            code0 = _sample(first, do_sample, top_k, top_p, temperature, rng)
            if code0 == codec_eos:
                break
            prev_first.append(code0)
            th = hidden[0, -1][None].astype(np.float32)
            codes16 = np.zeros((1, N_GROUPS), dtype=np.int64)
            codes16[0, 0] = code0
            for j in range(1, N_GROUPS):
                gl = self.predict_residual(th, codes16)
                codes16[0, j] = _sample(gl[0, j - 1], sub_do_sample, sub_top_k, sub_top_p,
                                        sub_temperature, rng)
            all_codes.append(codes16[0].copy())
            nxt = self.step_embed(codes16)[:, None] + trailing[:, None]    # [1,1,H]
            pos = np.broadcast_to(np.array([total]), (3, 1, 1)).copy()
            logits, hidden, past = self.talker_cache_step(
                nxt, pos, np.ones((1, total + 1), np.int64), past)
            total += 1
            if verbose and (step + 1) % 25 == 0:
                print(f"    …{step + 1} frames (cached)", file=sys.stderr)
        codes = np.stack(all_codes, axis=0).astype(np.int64) if all_codes \
            else np.zeros((0, N_GROUPS), np.int64)
        if verbose:
            print(f"  generated {codes.shape[0]} frames (KV-cache)")
        return codes

    def _generate_clone(self, text, ref_audio, ref_text, language="Auto", max_new_tokens=2048,
                        do_sample=True, top_k=50, top_p=1.0, temperature=0.9,
                        repetition_penalty=1.05, sub_do_sample=True, sub_top_k=50, sub_top_p=1.0,
                        sub_temperature=0.9, seed=0, verbose=True):
        """Base-model voice cloning (ICL), faithful to generate_icl_prompt (modeling L1968)
        + the x-vector speaker prompt. Reference audio → codes (tok_encoder) + x-vector
        (speaker_encoder); prompt = role + codec tags(+x-vector) + [ref_text+text+eos / codec_bos
        + per-frame ref-code sum]. Returns generated codes [T,16]."""
        if self.speaker_encoder is None:
            raise RuntimeError("speaker_encoder.onnx missing — export it for the Base model: "
                               "`uv run optimize.py --model base/1.7B --components speaker_encoder`.")
        if not ref_text:
            raise ValueError("voice clone requires --ref-text (transcript of --ref-audio).")
        cfg = self.cfg; tc = cfg["talker_config"]; H = tc["hidden_size"]
        tts_bos, tts_eos, tts_pad = (cfg["tts_bos_token_id"], cfg["tts_eos_token_id"],
                                     cfg["tts_pad_token_id"])
        codec_eos = tc["codec_eos_token_id"]
        codec_pad, codec_bos = tc["codec_pad_id"], tc["codec_bos_id"]; vocab = tc["vocab_size"]

        # reference audio → codes (tok_encoder, 1 s windows) + x-vector (speaker_encoder)
        wav = self._load_ref_wav(ref_audio)
        ref_code = self.encode_chunked(wav)                                  # [T_ref,16]
        spk = self.speaker_encoder.run(None, {"audio": wav[None].astype(np.float32)})[0]
        spk = spk.reshape(1, 1, H)                                           # x-vector [1,1,H]

        assistant = f"<|im_start|>assistant\n{text}<|im_end|>\n<|im_start|>assistant\n"
        input_id = self._ids(assistant)
        ref_id = self._ids(f"<|im_start|>assistant\n{ref_text}<|im_end|>\n")[:, 3:-2]
        text_id = input_id[:, 3:-5]

        spec = self.embed_text([[tts_bos, tts_eos, tts_pad]])
        bos_e, eos_e, pad_e = spec[:, 0:1], spec[:, 1:2], spec[:, 2:3]
        lang = (language or "auto").lower()
        language_id = (tc["codec_language_id"][lang]
                       if lang != "auto" and lang in tc.get("codec_language_id", {}) else None)
        codec_prefill = ([[tc["codec_nothink_id"], tc["codec_think_bos_id"], tc["codec_think_eos_id"]]]
                         if language_id is None else
                         [[tc["codec_think_id"], tc["codec_think_bos_id"], language_id,
                           tc["codec_think_eos_id"]]])
        codec0 = self.embed_codec(codec_prefill)
        codec1 = self.embed_codec([[codec_pad, codec_bos]])
        codec_input = np.concatenate([codec0, spk, codec1], axis=1)         # x-vector injected

        role = self.embed_text(input_id[:, :3])
        pad_block = np.concatenate([np.repeat(pad_e, codec_input.shape[1] - 2, axis=1), bos_e], axis=1)
        base = np.concatenate([role, pad_block + codec_input[:, :-1]], axis=1)

        # ICL block (generate_icl_prompt, non_streaming): the per-frame ref-code sum IS step_embed
        text_embed = np.concatenate([self.embed_text(np.concatenate([ref_id, text_id], axis=1)),
                                     eos_e], axis=1)                         # [1,T1,H]
        T1 = text_embed.shape[1]
        codec_embed = np.concatenate([self.embed_codec([[codec_bos]]),
                                      self.step_embed(ref_code)[None]], axis=1)   # [1,1+T_ref,H]
        icl = text_embed + self.embed_codec([[codec_pad] * T1])
        icl = np.concatenate([icl, codec_embed + pad_e], axis=1)
        talker_in = np.concatenate([base, icl], axis=1)
        trailing = pad_e[:, 0]
        if verbose:
            print(f"  [clone] ref {ref_code.shape[0]} frames + ref_text {ref_id.shape[1]} toks "
                  f"+ text {text_id.shape[1]} toks → prefill {talker_in.shape[1]}", file=sys.stderr)
        return self._ar_loop(talker_in, trailing, vocab, codec_eos, max_new_tokens, do_sample,
                             top_k, top_p, temperature, repetition_penalty, sub_do_sample,
                             sub_top_k, sub_top_p, sub_temperature, seed, verbose)


def selftest(pipe: Pipeline):
    """Codec round-trip + building-block smoke test on the loaded EP."""
    print(f"Provider: {pipe.provider}")
    rng = np.random.default_rng(0)
    t = np.arange(SR) / SR
    audio = (0.6 * np.sin(2 * np.pi * (180 + 300 * t) * t)
             + 0.01 * rng.standard_normal(SR)).astype(np.float32)[None, None, :]

    codes = pipe.encode(audio)
    print(f"  encode : audio{audio.shape} -> codes{codes.shape}")
    wav = pipe.decode_chunked(codes)
    print(f"  decode : codes{codes.shape} -> wav{wav.shape}")

    te = pipe.embed_text(rng.integers(0, 1000, (1, 8)))
    ce = pipe.embed_codec(rng.integers(0, 2048, (1, 8)))
    print(f"  text_embed{te.shape}  codec_embed{ce.shape}")
    th = rng.standard_normal((1, 2048)).astype(np.float32)
    gl = pipe.predict_residual(th, rng.integers(0, 2048, (1, N_GROUPS)))
    print(f"  code_predictor group_logits{gl.shape}")
    if pipe.residual_embed is not None:
        se = pipe.step_embed(rng.integers(0, 2048, (1, N_GROUPS)))
        print(f"  residual_embed step_embed{se.shape}")
    else:
        print("  [warn] residual_embed.onnx missing — re-export for generate()")
    print("OK — codec path + building blocks run on this EP.")


def main():
    ap = argparse.ArgumentParser(description="Qwen3-TTS ONNX inference")
    ap.add_argument("--model-path", required=True, help="onnx/{device}_{precision} dir")
    ap.add_argument("--tts-dir", help="HF model dir (config + tokenizer) — needed for --text")
    ap.add_argument("--selftest", action="store_true", help="codec round-trip + block smoke test")
    ap.add_argument("--text", help="text to synthesize (full generation)")
    ap.add_argument("--instruct", help="voice-design style instruction (VoiceDesign only)")
    ap.add_argument("--speaker", help="built-in speaker name (CustomVoice only)")
    ap.add_argument("--ref-audio", help="reference wav for voice cloning (Base only)")
    ap.add_argument("--ref-text", help="transcript of --ref-audio (Base clone)")
    ap.add_argument("--language", default="Auto", help="language (default Auto)")
    ap.add_argument("--out", default="out.wav", help="output wav path for --text")
    ap.add_argument("--max-new-tokens", type=int, default=2048)
    ap.add_argument("--greedy", action="store_true", help="disable sampling (argmax)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save-wav", help="write the self-test reconstruction to this path")
    args = ap.parse_args()

    pipe = Pipeline(args.model_path, tts_dir=args.tts_dir)

    if args.text is not None:
        print(f"  model_type={pipe.model_type}", file=sys.stderr)
        codes = pipe.generate(
            args.text, language=args.language, instruct=args.instruct,
            speaker=args.speaker, ref_audio=args.ref_audio, ref_text=args.ref_text,
            max_new_tokens=args.max_new_tokens,
            do_sample=not args.greedy, sub_do_sample=not args.greedy, seed=args.seed)
        if codes.shape[0] == 0:
            print("  [warn] no frames generated (immediate EOS)"); return
        wav = pipe.decode_chunked(codes[None]).reshape(-1)
        import soundfile as sf
        sf.write(args.out, wav, SR)
        print(f"  wrote {args.out}  ({wav.shape[0] / SR:.2f}s)")
        return

    if args.selftest:
        selftest(pipe)
        if args.save_wav:
            import soundfile as sf
            rng = np.random.default_rng(0)
            t = np.arange(SR) / SR
            audio = (0.6 * np.sin(2 * np.pi * (180 + 300 * t) * t)).astype(np.float32)[None, None, :]
            sf.write(args.save_wav, pipe.decode_chunked(pipe.encode(audio)).reshape(-1), SR)
            print(f"  wrote {args.save_wav}")
        return

    ap.error("nothing to do: pass --selftest or --text ...")


if __name__ == "__main__":
    main()