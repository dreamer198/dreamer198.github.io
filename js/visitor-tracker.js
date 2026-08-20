(function () {
  'use strict'

  var config = window.DREAMER_VISITOR_CONFIG || {}
  var apiBase = String(config.apiBase || '').replace(/\/$/, '')
  var isLocalhost = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)

  if (!config.enabled || !apiBase) return
  if (isLocalhost && !config.trackLocalhost) return

  var currentPath = null

  function emitVisitResult(data) {
    if (!data || !data.summary) return
    window.dispatchEvent(new CustomEvent('dreamer:visitor-summary', {
      detail: data
    }))
  }

  function reportVisit () {
    var path = window.location.pathname
    if (path === currentPath) return
    currentPath = path

    var wantsSummary = /^\/visitors\/?$/.test(path)
    var endpoint = apiBase + '/api/visit?' + (wantsSummary ? 'summary=1' : 'summary=0')

    window.fetch(endpoint, {
      method: 'POST',
      mode: 'cors',
      credentials: 'omit',
      keepalive: true
    }).then(function (response) {
      if (!response.ok) return null
      return response.json()
    }).then(emitVisitResult).catch(function () {})
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', reportVisit, { once: true })
  } else {
    reportVisit()
  }

  document.addEventListener('pjax:complete', reportVisit)
  window.addEventListener('popstate', function () {
    window.setTimeout(reportVisit, 0)
  })
})()
