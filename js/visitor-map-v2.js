(function () {
  'use strict'

  var state = {
    map: null,
    summary: null,
    observer: null
  }

  var CHINA_COUNTRY = { code: 'CN', name: '中国' }
  var UNKNOWN_COUNTRY = { code: 'XX', name: '未知地区' }
  var CHINA_REGION_CODES = ['CN', 'TW', 'HK', 'MO']

  function $(selector) {
    return document.querySelector(selector)
  }

  function formatNumber(value) {
    return new Intl.NumberFormat('zh-CN').format(Number(value) || 0)
  }

  function formatDate(value) {
    if (!value) return '等待第一次访问'
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(value))
  }

  function updateText(selector, value) {
    var node = $(selector)
    if (node) node.textContent = value
  }

  function setStatus(type, text) {
    var node = $('#visitor-map-status')
    if (!node) return
    node.className = 'visitor-map-status ' + (type || '')
    node.textContent = text || ''
  }

  function getCssVar(name, fallback) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
  }

  function disposeMap(container) {
    if (state.map) {
      try {
        state.map.destroy(false)
      } catch (error) {}
      state.map = null
    }

    if (container) {
      container.innerHTML = ''
      container.classList.remove('jvm-container')
      container.style.backgroundColor = ''
    }
  }

  function getApiBase() {
    var config = window.DREAMER_VISITOR_CONFIG || {}
    return String(config.apiBase || '').replace(/\/$/, '')
  }

  function isVisitorsPage() {
    return Boolean($('#visitor-world-map') && $('#visitor-map-status'))
  }

  function fetchWithTimeout(url, options, timeout) {
    var controller = window.AbortController ? new AbortController() : null
    var timer = null
    var requestOptions = options || {}

    if (controller) {
      requestOptions.signal = controller.signal
      timer = window.setTimeout(function () {
        controller.abort()
      }, timeout)
    }

    return window.fetch(url, requestOptions).finally(function () {
      if (timer) window.clearTimeout(timer)
    })
  }

  function normalizeRegionCode(code) {
    var normalizedCode = String(code || '').trim().toUpperCase()
    if (!/^[A-Z]{2}$/.test(normalizedCode)) return UNKNOWN_COUNTRY.code
    return CHINA_REGION_CODES.indexOf(normalizedCode) > -1 ? CHINA_COUNTRY.code : normalizedCode
  }

  function isChinaRegionCode(code) {
    return CHINA_REGION_CODES.indexOf(String(code || '').trim().toUpperCase()) > -1
  }

  function displayNameForCode(code, fallbackName) {
    if (code === CHINA_COUNTRY.code) return CHINA_COUNTRY.name
    if (code === UNKNOWN_COUNTRY.code) return UNKNOWN_COUNTRY.name
    return fallbackName || code
  }

  function latestSeen(left, right) {
    if (!left) return right || null
    if (!right) return left
    return new Date(left).getTime() >= new Date(right).getTime() ? left : right
  }

  function normalizeSummary(summary) {
    summary = summary || {}
    var buckets = {}

    ;(summary.countries || []).forEach(function (item) {
      var code = normalizeRegionCode(item.code)
      var bucket = buckets[code] || {
        code: code,
        name: displayNameForCode(code, item.name),
        count: 0,
        lastSeen: null
      }

      bucket.name = displayNameForCode(code, bucket.name)
      bucket.count += Number(item.count) || 0
      bucket.lastSeen = latestSeen(bucket.lastSeen, item.lastSeen)
      buckets[code] = bucket
    })

    var countries = Object.keys(buckets).map(function (code) {
      return buckets[code]
    }).filter(function (item) {
      return item.count > 0
    }).sort(function (a, b) {
      return b.count - a.count || a.name.localeCompare(b.name, 'zh-CN')
    })

    var totalVisitors = countries.reduce(function (total, item) {
      return total + item.count
    }, 0)

    countries.forEach(function (item) {
      item.ratio = totalVisitors ? Math.round((item.count / totalVisitors) * 10000) / 10000 : 0
    })

    return {
      updatedAt: summary.updatedAt || countries.reduce(function (latest, item) {
        return latestSeen(latest, item.lastSeen)
      }, null),
      totalVisitors: totalVisitors,
      totalCountries: countries.length,
      countries: countries
    }
  }

  function toSeries(summary) {
    var series = (summary.countries || []).reduce(function (series, item) {
      if (item.code && item.code !== 'XX') series[item.code] = item.count
      return series
    }, {})

    if (series[CHINA_COUNTRY.code]) {
      CHINA_REGION_CODES.forEach(function (code) {
        series[code] = series[CHINA_COUNTRY.code]
      })
    }

    return series
  }

  function findCountry(summary, code) {
    return (summary.countries || []).find(function (item) {
      return item.code === code
    })
  }

  function syncChinaRegions(summary) {
    if (!state.map || !state.map.regions) return

    var china = findCountry(summary, CHINA_COUNTRY.code)
    var landFill = getCssVar('--visitor-map-land', '#dce7ed')
    var chinaFill = landFill

    if (china && state.map.regions[CHINA_COUNTRY.code]) {
      var chinaNode = state.map.regions[CHINA_COUNTRY.code].element.shape.node
      chinaFill = chinaNode.dataset.visitorChinaBaseFill || chinaNode.getAttribute('fill') || getComputedStyle(chinaNode).fill || getCssVar('--visitor-map-high', '#1b7f8c')
      chinaNode.dataset.visitorChinaBaseFill = chinaFill
    }

    CHINA_REGION_CODES.forEach(function (code) {
      var region = state.map.regions[code]
      if (!region) return

      var node = region.element.shape.node
      var isMainland = code === CHINA_COUNTRY.code
      var baseFill = china ? chinaFill : landFill
      node.dataset.visitorChinaBaseFill = baseFill
      region.element.setStyle({
        fill: baseFill,
        stroke: isMainland ? getCssVar('--visitor-map-border', 'rgba(255,255,255,0.62)') : baseFill,
        strokeWidth: isMainland ? 0.35 : 0,
        cursor: china ? 'pointer' : 'default'
      })
      node.classList.add('visitor-china-merged-region')
      node.setAttribute('data-display-code', CHINA_COUNTRY.code)
      node.setAttribute('aria-label', CHINA_COUNTRY.name)
    })
  }

  function setChinaRegionsHover(active, summary) {
    if (!state.map || !state.map.regions) return

    if (!active) {
      syncChinaRegions(summary)
      return
    }

    var hoverFill = getCssVar('--blog-accent-2', '#2d6cdf')
    CHINA_REGION_CODES.forEach(function (code) {
      var region = state.map.regions[code]
      if (!region) return

      region.element.setStyle({
        fill: hoverFill,
        stroke: hoverFill,
        strokeWidth: 0,
        cursor: 'pointer'
      })
    })
  }

  function bindChinaRegionHover(summary) {
    if (!state.map || !state.map.regions) return

    CHINA_REGION_CODES.forEach(function (code) {
      var region = state.map.regions[code]
      if (!region || !region.element || !region.element.shape) return

      var node = region.element.shape.node
      if (node.dataset.visitorChinaHoverBound) return
      node.dataset.visitorChinaHoverBound = 'true'
      node.addEventListener('mouseenter', function () {
        setChinaRegionsHover(true, summary)
      })
      node.addEventListener('mouseleave', function () {
        setChinaRegionsHover(false, summary)
      })
      node.addEventListener('focus', function () {
        setChinaRegionsHover(true, summary)
      })
      node.addEventListener('blur', function () {
        setChinaRegionsHover(false, summary)
      })
    })
  }

  function renderStats(summary) {
    updateText('[data-visitor-total]', formatNumber(summary.totalVisitors))
    updateText('[data-visitor-countries]', formatNumber(summary.totalCountries))
    updateText('[data-visitor-updated]', formatDate(summary.updatedAt))
  }

  function renderTopList(summary) {
    var list = $('#visitor-country-list')
    if (!list) return

    var countries = (summary.countries || []).slice(0, 10)
    if (!countries.length) {
      list.innerHTML = '<li class="visitor-country-empty">还没有公开统计数据</li>'
      return
    }

    list.innerHTML = countries.map(function (item, index) {
      var percent = Math.round((item.ratio || 0) * 1000) / 10
      return [
        '<li class="visitor-country-item">',
        '<span class="visitor-country-rank">', index + 1, '</span>',
        '<span class="visitor-country-main">',
        '<span class="visitor-country-name">', item.name, '</span>',
        '<span class="visitor-country-bar"><span style="width:', Math.max(percent, 4), '%"></span></span>',
        '</span>',
        '<span class="visitor-country-count">', formatNumber(item.count), '</span>',
        '</li>'
      ].join('')
    }).join('')
  }

  function renderMap(summary) {
    var container = $('#visitor-world-map')
    if (!container) return
    disposeMap(container)

    if (!window.jsVectorMap) {
      setStatus('error', '地图组件加载失败，请稍后刷新。')
      return
    }

    var series = toSeries(summary)

    state.map = new window.jsVectorMap({
      selector: '#visitor-world-map',
      map: 'world',
      backgroundColor: 'transparent',
      zoomButtons: false,
      zoomOnScroll: false,
      regionStyle: {
        initial: {
          fill: getCssVar('--visitor-map-land', '#dce7ed'),
          stroke: getCssVar('--visitor-map-border', 'rgba(255,255,255,0.62)'),
          strokeWidth: 0.35
        },
        hover: {
          fill: getCssVar('--blog-accent-2', '#2d6cdf')
        }
      },
      visualizeData: {
        scale: [
          getCssVar('--visitor-map-low', '#8fd1d4'),
          getCssVar('--visitor-map-high', '#1b7f8c')
        ],
        values: series
      },
      onRegionTooltipShow: function (event, tooltip, code) {
        var normalizedCode = normalizeRegionCode(code)
        var match = (summary.countries || []).find(function (item) { return item.code === normalizedCode })
        if (isChinaRegionCode(code)) setChinaRegionsHover(true, summary)
        if (match) {
          tooltip.text(match.name + ': ' + formatNumber(match.count) + ' 次访问')
        } else {
          event.preventDefault()
        }
      }
    })

    syncChinaRegions(summary)
    bindChinaRegionHover(summary)
    window.requestAnimationFrame(function () {
      if (!state.map) return
      state.map.updateSize()
      syncChinaRegions(summary)
      bindChinaRegionHover(summary)
    })
  }

  async function loadSummary() {
    var apiBase = getApiBase()

    if (!apiBase) {
      setStatus('warning', '访客统计接口尚未配置，部署 Worker 后在 visitor-config.js 中填入 apiBase。')
      renderStats({ totalVisitors: 0, totalCountries: 0, updatedAt: null, countries: [] })
      renderTopList({ countries: [] })
      return
    }

    setStatus('loading', '正在加载访客来源数据...')

    try {
      var response = await fetchWithTimeout(apiBase + '/api/summary?_=' + Date.now(), {
        mode: 'cors',
        credentials: 'omit',
        cache: 'no-store'
      }, 8000)

      if (!response.ok) throw new Error('HTTP ' + response.status)

      var summary = normalizeSummary(await response.json())
      renderSummary(summary)
      setStatus('', summary.totalVisitors ? '数据已更新' : '等待第一次访问')
    } catch (error) {
      setStatus('error', '暂时无法加载访客来源数据，请稍后再试。')
      renderStats({ totalVisitors: 0, totalCountries: 0, updatedAt: null, countries: [] })
      renderTopList({ countries: [] })
    }
  }

  function renderSummary(summary) {
    state.summary = summary
    renderStats(summary)
    renderTopList(summary)
    renderMap(summary)
  }

  function init() {
    if (!isVisitorsPage()) return
    loadSummary()

    if (!state.observer) {
      state.observer = new MutationObserver(function () {
        if (isVisitorsPage() && state.summary) renderMap(state.summary)
      })
      state.observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme']
      })
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true })
  } else {
    init()
  }

  document.addEventListener('pjax:complete', init)
  window.addEventListener('dreamer:visitor-summary', function (event) {
    if (!isVisitorsPage() || !event.detail || !event.detail.summary) return
    renderSummary(normalizeSummary(event.detail.summary))
    setStatus('', event.detail.counted ? '已计入本次打开' : '统计已同步')
  })
})()
