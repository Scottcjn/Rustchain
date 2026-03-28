/**
 * BoTTube Embed Loader  v1.0.0
 * ==============================
 * Drop-in script to embed BoTTube videos on any page.
 *
 * Usage:
 *   <script src="https://embed.bottube.io/embed/bottube-embed.js"></script>
 *
 *   <!-- Auto-discover mode -->
 *   <div class="bottube-player" data-video="abc123" data-width="640" data-height="360"></div>
 *
 *   <!-- Programmatic mode -->
 *   <div id="my-player"></div>
 *   <script>
 *     const player = new BoTTubePlayer("my-player", "abc123", { theme: "dark" });
 *     player.on("ready", () => player.play());
 *   </script>
 */

(function (global) {
  "use strict";

  // -------------------------------------------------------------------------
  // Config
  // -------------------------------------------------------------------------
  var DEFAULT_EMBED_BASE = "https://embed.bottube.io";
  var DEFAULT_WIDTH      = 640;
  var DEFAULT_HEIGHT     = 360;
  var IFRAME_STYLE = [
    "border:none",
    "display:block",
    "width:100%",
    "height:100%",
  ].join(";");

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------
  function buildEmbedUrl(videoId, opts) {
    var base = (opts.embedBase || DEFAULT_EMBED_BASE).replace(/\/$/, "");
    var params = [];
    if (opts.autoplay)  params.push("autoplay=1");
    if (opts.theme)     params.push("theme=" + encodeURIComponent(opts.theme));
    if (opts.startTime) params.push("t="     + encodeURIComponent(opts.startTime));
    var qs = params.length ? "?" + params.join("&") : "";
    return base + "/embed/" + encodeURIComponent(videoId) + qs;
  }

  function createWrapper(width, height) {
    var wrap = document.createElement("div");
    wrap.style.cssText = [
      "position:relative",
      "width:" + (typeof width  === "number" ? width  + "px" : width),
      "height:" + (typeof height === "number" ? height + "px" : height),
      "overflow:hidden",
      "background:#000",
    ].join(";");
    return wrap;
  }

  // -------------------------------------------------------------------------
  // BoTTubePlayer class
  // -------------------------------------------------------------------------
  /**
   * @param {string|Element} container  CSS id or DOM element to embed into
   * @param {string}         videoId    BoTTube video identifier
   * @param {object}         [opts]     Optional config
   *   opts.embedBase  {string}  Base URL of embed server
   *   opts.width      {number}  Player width in px (default 640)
   *   opts.height     {number}  Player height in px (default 360)
   *   opts.autoplay   {boolean} Start playback immediately (default false)
   *   opts.theme      {string}  "dark" | "light" (default "dark")
   *   opts.startTime  {number}  Start offset in seconds (default 0)
   */
  function BoTTubePlayer(container, videoId, opts) {
    opts = opts || {};
    this.videoId = videoId;
    this._handlers = {};
    this._ready    = false;

    // Resolve container
    var el = typeof container === "string"
      ? document.getElementById(container)
      : container;
    if (!el) throw new Error("BoTTubePlayer: container not found: " + container);

    // Build wrapper + iframe
    var width  = opts.width  || parseInt(el.dataset.width,  10) || DEFAULT_WIDTH;
    var height = opts.height || parseInt(el.dataset.height, 10) || DEFAULT_HEIGHT;
    var wrap   = createWrapper(width, height);

    this._iframe = document.createElement("iframe");
    this._iframe.src             = buildEmbedUrl(videoId, opts);
    this._iframe.style.cssText   = IFRAME_STYLE;
    this._iframe.allow           = "autoplay; fullscreen; picture-in-picture";
    this._iframe.allowFullscreen = true;
    this._iframe.title           = "BoTTube Player – " + videoId;

    wrap.appendChild(this._iframe);
    el.innerHTML = "";
    el.appendChild(wrap);

    // Listen for postMessage events from the iframe
    var self = this;
    this._msgHandler = function (event) {
      var data = event.data;
      if (!data || typeof data.type !== "string") return;
      if (!data.type.startsWith("bottube:"))      return;
      if (data.videoId !== self.videoId)          return;
      var evtName = data.type.slice("bottube:".length); // e.g. "play"
      if (evtName === "ready" || evtName === "loaded") self._ready = true;
      self._emit(evtName, data);
    };
    window.addEventListener("message", this._msgHandler);
  }

  /** Send a postMessage command to the embedded iframe. */
  BoTTubePlayer.prototype._send = function (type, payload) {
    var msg = Object.assign({ type: "bottube:" + type, videoId: this.videoId }, payload || {});
    this._iframe.contentWindow.postMessage(msg, "*");
  };

  /** Register an event listener. */
  BoTTubePlayer.prototype.on = function (event, fn) {
    if (!this._handlers[event]) this._handlers[event] = [];
    this._handlers[event].push(fn);
    return this; // chainable
  };

  /** Remove an event listener. */
  BoTTubePlayer.prototype.off = function (event, fn) {
    if (!this._handlers[event]) return this;
    this._handlers[event] = this._handlers[event].filter(function (h) { return h !== fn; });
    return this;
  };

  /** Emit an event internally. */
  BoTTubePlayer.prototype._emit = function (event, data) {
    var handlers = this._handlers[event] || [];
    handlers.forEach(function (fn) { fn(data); });
  };

  /** Start playback. */
  BoTTubePlayer.prototype.play = function ()  { this._send("play");  return this; };

  /** Pause playback. */
  BoTTubePlayer.prototype.pause = function () { this._send("pause"); return this; };

  /** Seek to a time in seconds. */
  BoTTubePlayer.prototype.seek = function (seconds) {
    this._send("seek", { time: seconds });
    return this;
  };

  /** Set volume (0.0 – 1.0). */
  BoTTubePlayer.prototype.setVolume = function (vol) {
    this._send("volume", { volume: Math.max(0, Math.min(1, vol)) });
    return this;
  };

  /** Mute or unmute. */
  BoTTubePlayer.prototype.mute   = function () { this._send("mute", { muted: true  }); return this; };
  BoTTubePlayer.prototype.unmute = function () { this._send("mute", { muted: false }); return this; };

  /** Request the current playback state (fires a "state" event). */
  BoTTubePlayer.prototype.getState = function () { this._send("getState"); return this; };

  /** Destroy the player and remove the iframe. */
  BoTTubePlayer.prototype.destroy = function () {
    window.removeEventListener("message", this._msgHandler);
    this._iframe.parentNode && this._iframe.parentNode.removeChild(this._iframe);
    this._handlers = {};
  };

  // -------------------------------------------------------------------------
  // Auto-discover <div class="bottube-player" data-video="ID"> elements
  // -------------------------------------------------------------------------
  function autoDiscover() {
    var divs = document.querySelectorAll(".bottube-player[data-video]");
    divs.forEach(function (div) {
      if (div.dataset.bottubeMounted) return; // already mounted
      div.dataset.bottubeMounted = "1";
      var videoId = div.dataset.video;
      if (!videoId) return;
      try {
        var player = new BoTTubePlayer(div, videoId, {
          autoplay:  div.dataset.autoplay === "1" || div.dataset.autoplay === "true",
          theme:     div.dataset.theme     || "dark",
          startTime: parseInt(div.dataset.startTime || "0", 10) || 0,
          width:     parseInt(div.dataset.width,  10) || DEFAULT_WIDTH,
          height:    parseInt(div.dataset.height, 10) || DEFAULT_HEIGHT,
        });
        div._bottube = player;
      } catch (err) {
        console.error("BoTTube: failed to mount player for", videoId, err);
      }
    });
  }

  // Run auto-discover on DOM ready or immediately if already ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoDiscover);
  } else {
    autoDiscover();
  }

  // -------------------------------------------------------------------------
  // Export
  // -------------------------------------------------------------------------
  global.BoTTubePlayer = BoTTubePlayer;

})(typeof window !== "undefined" ? window : this);
