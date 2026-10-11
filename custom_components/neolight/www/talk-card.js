/* NeoLight microphone card. Audio stays in the browser and the local HA bridge. */
class NeoLightTalkCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._phase = 0;
    this._sum = 0;
    this._count = 0;
    this._audio = [];
    this._sending = Promise.resolve();
    this._onVisibility = () => {
      if (document.hidden) void this._stop();
    };
  }

  setConfig(config) {
    if (!config.camera || !config.camera.startsWith("camera.")) {
      throw new Error("NeoLight Talk requires a camera entity");
    }
    this._config = config;
    this._render();
  }

  set hass(value) {
    this._hass = value;
    this._update();
  }

  getCardSize() { return 2; }

  connectedCallback() {
    document.addEventListener("visibilitychange", this._onVisibility);
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._onVisibility);
    void this._stop();
  }

  _label(en, ru) {
    return /^(ru|uk)/.test(this._hass?.language || navigator.language) ? ru : en;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .title { font-size: 18px; font-weight: 500; }
        .status { margin: 12px 0; min-height: 20px; color: var(--secondary-text-color); }
        .actions { display: flex; gap: 8px; }
        button { border: 0; border-radius: 10px; padding: 11px 16px; cursor: pointer;
          background: var(--primary-color); color: var(--text-primary-color, white); }
        button.secondary { background: var(--secondary-background-color); color: var(--primary-text-color); }
        button:disabled { opacity: .5; cursor: default; }
      </style>
      <ha-card>
        <div class="row"><div class="title"></div><ha-icon icon="mdi:doorbell-video"></ha-icon></div>
        <div class="status" role="status"></div>
        <div class="actions"><button class="talk" type="button"></button>
          <button class="secondary camera" type="button"></button></div>
      </ha-card>`;
    this.shadowRoot.querySelector(".talk").addEventListener("click", () => {
      void (this._talking ? this._stop() : this._start());
    });
    this.shadowRoot.querySelector(".camera").addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-more-info", {
        bubbles: true, composed: true, detail: { entityId: this._config.camera },
      }));
    });
    this._update();
  }

  _update() {
    if (!this._config || !this._hass || !this.shadowRoot.querySelector(".status")) return;
    const call = this._config.call_entity && this._hass.states[this._config.call_entity];
    const camera = this._hass.states[this._config.camera];
    this.shadowRoot.querySelector(".title").textContent = this._config.title || "NeoLight";
    this.shadowRoot.querySelector(".talk").textContent = this._talking
      ? this._label("End conversation", "Завершить разговор")
      : this._label("Talk", "Говорить");
    this.shadowRoot.querySelector(".talk").disabled = this._busy;
    this.shadowRoot.querySelector(".camera").textContent = this._label("Open camera", "Открыть камеру");
    const state = this._talking ? this._label("Microphone active", "Микрофон включён")
      : call?.state === "ringing" ? this._label("Ringing", "Звонит")
      : call?.state === "answered" ? this._label("Conversation active", "Идёт разговор")
      : camera?.state === "unavailable" ? this._label("Camera unavailable", "Камера недоступна")
      : this._label("Ready", "Готово");
    this.shadowRoot.querySelector(".status").textContent = this._error || state;
  }

  static _mulaw(sample) {
    let pcm = Math.max(-32768, Math.min(32767, Math.round(sample * 32768)));
    const sign = pcm < 0 ? 0x80 : 0;
    pcm = Math.min(Math.abs(pcm), 32635) + 132;
    let exponent = 7;
    for (let mask = 0x4000; exponent > 0 && !(pcm & mask); mask >>= 1) exponent--;
    const mantissa = (pcm >> (exponent + 3)) & 0x0f;
    return (~(sign | (exponent << 4) | mantissa)) & 0xff;
  }

  _capture(samples) {
    if (!this._talking) return;
    const step = 8000 / this._context.sampleRate;
    for (let index = 0; index < samples.length; index++) {
      this._sum += samples[index];
      this._count++;
      this._phase += step;
      if (this._phase >= 1) {
        this._audio.push(NeoLightTalkCard._mulaw(this._sum / this._count));
        this._phase -= 1;
        this._sum = 0;
        this._count = 0;
      }
    }
    if (this._audio.length >= 2560) this._flush();
  }

  _flush() {
    if (!this._talking || this._audio.length < 320) return;
    const count = Math.min(Math.floor(this._audio.length / 320) * 320, 3200);
    const bytes = this._audio.splice(0, count);
    const encoded = btoa(String.fromCharCode(...bytes));
    const entryId = this._session.entry_id;
    const token = this._session.token;
    this._sending = this._sending.then(() => this._hass.connection.sendMessagePromise({
      type: "neolight/talk_audio", entry_id: entryId, token, audio: encoded,
    })).catch((error) => {
      this._error = String(error);
      void this._stop();
    });
  }

  async _start() {
    if (this._busy || this._talking) return;
    this._busy = true;
    this._error = "";
    this._update();
    try {
      this._stream = await navigator.mediaDevices.getUserMedia({ audio: {
        echoCancellation: true, noiseSuppression: true, autoGainControl: true,
      } });
      if (!this.isConnected) throw new Error("NeoLight Talk card was closed");
      this._context = new AudioContext();
      this._source = this._context.createMediaStreamSource(this._stream);
      this._processor = this._context.createScriptProcessor(2048, 1, 1);
      this._processor.onaudioprocess = (event) => this._capture(event.inputBuffer.getChannelData(0));
      this._source.connect(this._processor);
      this._silence = this._context.createGain();
      this._silence.gain.value = 0;
      this._processor.connect(this._silence);
      this._silence.connect(this._context.destination);
      await this._context.resume();
      const response = await this._hass.connection.sendMessagePromise({
        type: "neolight/talk_start", camera: this._config.camera,
      });
      this._session = response?.result || response;
      if (!this._session?.token) throw new Error("NeoLight talk session did not start");
      if (!this.isConnected) throw new Error("NeoLight Talk card was closed");
      this._talking = true;
    } catch (error) {
      this._error = String(error);
      await this._stop();
    } finally {
      this._busy = false;
      this._update();
    }
  }

  async _stop() {
    if (this._stopping) return;
    this._stopping = true;
    this._talking = false;
    const session = this._session;
    this._session = null;
    this._processor?.disconnect();
    this._source?.disconnect();
    this._silence?.disconnect();
    this._stream?.getTracks().forEach((track) => track.stop());
    this._stream = null;
    if (this._context && this._context.state !== "closed") await this._context.close();
    this._context = null;
    this._audio = [];
    this._phase = 0;
    this._sum = 0;
    this._count = 0;
    if (session && this._hass) {
      try {
        await this._hass.connection.sendMessagePromise({
          type: "neolight/talk_stop", entry_id: session.entry_id, token: session.token,
        });
      } catch (_) { /* The server lease will close the native socket. */ }
    }
    this._stopping = false;
    this._update();
  }
}

customElements.define("neolight-talk-card", NeoLightTalkCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "neolight-talk-card", name: "NeoLight Talk", preview: false,
  description: "Browser microphone for a NeoLight door camera",
});
