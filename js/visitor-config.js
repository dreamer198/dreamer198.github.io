(function () {
  var isLocalhost = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)

  window.DREAMER_VISITOR_CONFIG = {
    apiBase: isLocalhost
      ? 'http://127.0.0.1:8787'
      : 'https://dreamer-island-visitor-stats.dreamer198.workers.dev',
    enabled: true,
    trackLocalhost: true
  }
})()
