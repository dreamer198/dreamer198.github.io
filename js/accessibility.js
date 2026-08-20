(function () {
  'use strict'

  var CLICKABLES = [
    ['#search-button > .search', '搜索', true],
    ['#toggle-menu', '打开导航菜单', false],
    ['#scroll-down', '向下浏览文章列表', false]
  ]
  var lastSearchTrigger = null

  function isVisible(element) {
    return Boolean(element && !element.hidden && element.getClientRects().length && getComputedStyle(element).display !== 'none')
  }

  function makeKeyboardClickable(selector, label, opensDialog) {
    var element = document.querySelector(selector)
    if (!element) return

    if (!element.hasAttribute('role')) element.setAttribute('role', 'button')
    if (!element.hasAttribute('tabindex')) element.setAttribute('tabindex', '0')
    if (!element.hasAttribute('aria-label')) element.setAttribute('aria-label', label)
    if (opensDialog) {
      element.setAttribute('aria-haspopup', 'dialog')
      if (!element.hasAttribute('aria-expanded')) element.setAttribute('aria-expanded', 'false')
    }
    if (element.dataset.keyboardClickReady === 'true') return

    element.dataset.keyboardClickReady = 'true'
    element.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') return
      event.preventDefault()
      element.click()
    })
  }

  function normalizePath(value) {
    var path = value || '/'
    try { path = decodeURIComponent(path) } catch (error) {}
    path = path.replace(/\/index\.html$/, '/').replace(/\/{2,}/g, '/')
    return path.length > 1 ? path.replace(/\/$/, '') : '/'
  }

  function setActiveNavigation() {
    var current = normalizePath(window.location.pathname)
    document.querySelectorAll('#menus .site-page[aria-current], #sidebar-menus .site-page[aria-current]').forEach(function (item) {
      item.removeAttribute('aria-current')
    })
    document.querySelectorAll('#menus .menus_item.is-current, #sidebar-menus .menus_item.is-current').forEach(function (item) {
      item.classList.remove('is-current')
    })

    document.querySelectorAll('#menus, #sidebar-menus').forEach(function (container) {
      var links = Array.from(container.querySelectorAll('a.site-page[href]'))
      var active = links.find(function (link) {
        var target = normalizePath(new URL(link.href, window.location.href).pathname)
        if (target === '/') return current === '/' || current.indexOf('/page/') === 0
        if (['/archives', '/categories', '/tags'].indexOf(target) > -1) return current === target || current.indexOf(target + '/') === 0
        return current === target
      })

      if (!active) return
      active.setAttribute('aria-current', 'page')
      var item = active.closest('.menus_item')
      if (item) item.classList.add('is-current')
    })
  }

  function focusableElements(container) {
    return Array.from(container.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter(isVisible)
  }

  function enhanceSearchDialog() {
    var dialog = document.querySelector('#local-search .search-dialog')
    var title = document.querySelector('#local-search .search-dialog-title')
    var input = document.querySelector('#local-search .local-search-input input')
    var closeButton = document.querySelector('#local-search .search-close-button')
    var trigger = document.querySelector('#search-button > .search')
    var mask = document.querySelector('#search-mask')

    if (title) title.id = title.id || 'local-search-title'
    if (dialog) {
      dialog.setAttribute('role', 'dialog')
      dialog.setAttribute('aria-modal', 'true')
      dialog.setAttribute('aria-hidden', isVisible(dialog) ? 'false' : 'true')
      if (title) dialog.setAttribute('aria-labelledby', title.id)
    }
    if (input && !input.hasAttribute('aria-label')) input.setAttribute('aria-label', '搜索博客文章')
    if (closeButton) {
      closeButton.setAttribute('type', 'button')
      closeButton.setAttribute('aria-label', '关闭搜索')
    }
    if (trigger && trigger.dataset.searchFocusReady !== 'true') {
      trigger.dataset.searchFocusReady = 'true'
      trigger.addEventListener('click', function () {
        lastSearchTrigger = trigger
        window.setTimeout(function () {
          var open = isVisible(dialog)
          if (dialog) dialog.setAttribute('aria-hidden', open ? 'false' : 'true')
          trigger.setAttribute('aria-expanded', open ? 'true' : 'false')
        }, 20)
      }, true)
    }
    if (!dialog || dialog.dataset.focusTrapReady === 'true') return

    dialog.dataset.focusTrapReady = 'true'
    var wasOpen = isVisible(dialog)
    var syncState = function () {
      var open = isVisible(dialog)
      dialog.setAttribute('aria-hidden', open ? 'false' : 'true')
      var currentTrigger = document.querySelector('#search-button > .search')
      if (currentTrigger) currentTrigger.setAttribute('aria-expanded', open ? 'true' : 'false')
      if (wasOpen && !open && lastSearchTrigger && document.contains(lastSearchTrigger)) {
        lastSearchTrigger.focus({ preventScroll: true })
      }
      wasOpen = open
    }

    var observer = new MutationObserver(syncState)
    observer.observe(dialog, { attributes: true, attributeFilter: ['style', 'class', 'hidden'] })
    if (mask) observer.observe(mask, { attributes: true, attributeFilter: ['style', 'class', 'hidden'] })

    dialog.addEventListener('keydown', function (event) {
      if (event.key !== 'Tab' || !isVisible(dialog)) return
      var focusable = focusableElements(dialog)
      if (!focusable.length) {
        event.preventDefault()
        return
      }
      var first = focusable[0]
      var last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    })

    dialog.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape' || !isVisible(dialog) || !closeButton) return
      closeButton.click()
      window.setTimeout(syncState, 520)
    })
  }

  function closeQrPopover(wrapper, restoreFocus) {
    var button = wrapper.querySelector('.qr-social-button')
    var popover = wrapper.querySelector('.qr-social-popover')
    if (!button || !popover || popover.hidden) return
    popover.hidden = true
    button.setAttribute('aria-expanded', 'false')
    wrapper.classList.remove('is-open')
    if (restoreFocus) button.focus({ preventScroll: true })
  }

  function setupQrSocial() {
    document.querySelectorAll('.qr-social-wrap').forEach(function (wrapper) {
      if (wrapper.dataset.qrReady === 'true') return
      wrapper.dataset.qrReady = 'true'
      var button = wrapper.querySelector('.qr-social-button')
      var popover = wrapper.querySelector('.qr-social-popover')
      var closeButton = wrapper.querySelector('.qr-social-close')
      if (!button || !popover) return

      button.addEventListener('click', function () {
        var willOpen = popover.hidden
        document.querySelectorAll('.qr-social-wrap.is-open').forEach(function (openWrapper) {
          if (openWrapper !== wrapper) closeQrPopover(openWrapper, false)
        })
        popover.hidden = !willOpen
        button.setAttribute('aria-expanded', willOpen ? 'true' : 'false')
        wrapper.classList.toggle('is-open', willOpen)
        if (willOpen && closeButton) closeButton.focus({ preventScroll: true })
      })
      if (closeButton) closeButton.addEventListener('click', function () { closeQrPopover(wrapper, true) })
      wrapper.addEventListener('focusout', function () {
        window.setTimeout(function () {
          if (!wrapper.contains(document.activeElement)) closeQrPopover(wrapper, false)
        }, 0)
      })
    })
  }

  function setupTagFilter() {
    var input = document.getElementById('tag-filter-input')
    var cloud = document.querySelector('#body-wrap.type-tags .tag-cloud-list')
    var status = document.getElementById('tag-filter-status')
    if (!input || !cloud || input.dataset.filterReady === 'true') return
    input.dataset.filterReady = 'true'
    var tags = Array.from(cloud.querySelectorAll('a'))

    var filter = function () {
      var query = input.value.trim().toLocaleLowerCase('zh-CN')
      var visible = 0
      tags.forEach(function (tag) {
        var match = !query || tag.textContent.toLocaleLowerCase('zh-CN').indexOf(query) > -1
        tag.hidden = !match
        if (match) visible += 1
      })
      if (status) status.textContent = query ? '找到 ' + visible + ' 个标签' : '共 ' + tags.length + ' 个标签'
      cloud.classList.toggle('is-empty', visible === 0)
    }

    input.addEventListener('input', filter)
    filter()
  }

  function updateScrollEdges(element) {
    var scrollable = element.scrollWidth - element.clientWidth > 2
    element.classList.toggle('is-scrollable', scrollable)
    element.classList.toggle('is-at-start', !scrollable || element.scrollLeft <= 2)
    element.classList.toggle('is-at-end', !scrollable || element.scrollLeft + element.clientWidth >= element.scrollWidth - 2)
  }

  function makeKeyboardControl(element, label) {
    if (!element) return
    element.setAttribute('role', 'button')
    element.setAttribute('tabindex', '0')
    element.setAttribute('aria-label', label)
    if (element.dataset.keyboardControlReady === 'true') return

    element.dataset.keyboardControlReady = 'true'
    element.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') return
      event.preventDefault()
      element.click()
    })
  }

  function syncCodeExpandState(button) {
    var expanded = button.classList.contains('expand-done')
    button.setAttribute('aria-expanded', String(expanded))
    button.setAttribute('aria-label', expanded ? '收起代码' : '展开代码')
  }

  function enhanceScrollableRegions() {
    document.querySelectorAll('.table-wrap').forEach(function (wrapper) {
      if (wrapper.dataset.scrollA11yReady === 'true') return
      wrapper.dataset.scrollA11yReady = 'true'
      wrapper.setAttribute('tabindex', '0')
      wrapper.setAttribute('role', 'region')
      wrapper.setAttribute('aria-label', '可横向滚动的数据表格')
      wrapper.addEventListener('scroll', function () { updateScrollEdges(wrapper) }, { passive: true })
      updateScrollEdges(wrapper)
    })

    document.querySelectorAll('figure.highlight').forEach(function (block) {
      var language = Array.from(block.classList).find(function (name) { return name !== 'highlight' }) || 'text'
      var scroller = block.querySelector('table') || block
      if (scroller.dataset.codeScrollA11yReady !== 'true') {
        scroller.dataset.codeScrollA11yReady = 'true'
        scroller.setAttribute('tabindex', '0')
        scroller.setAttribute('role', 'region')
        scroller.setAttribute('aria-label', language + ' 代码，可横向滚动')
        scroller.addEventListener('scroll', function () { updateScrollEdges(scroller) }, { passive: true })
        updateScrollEdges(scroller)
      }

      var copyButton = block.querySelector('.copy-button')
      makeKeyboardControl(copyButton, '复制代码')
      var copyNotice = block.querySelector('.copy-notice')
      if (copyNotice) {
        copyNotice.setAttribute('aria-live', 'polite')
        copyNotice.setAttribute('aria-atomic', 'true')
      }

      var expandButton = block.querySelector('.code-expand-btn')
      if (expandButton) {
        makeKeyboardControl(expandButton, '展开代码')
        syncCodeExpandState(expandButton)
        if (expandButton.dataset.expandA11yReady !== 'true') {
          expandButton.dataset.expandA11yReady = 'true'
          expandButton.addEventListener('click', function () { syncCodeExpandState(expandButton) })
        }
      }
    })
  }

  function secureExternalLinks() {
    document.querySelectorAll('a[target="_blank"]').forEach(function (link) {
      var rel = new Set((link.getAttribute('rel') || '').split(/\s+/).filter(Boolean))
      rel.add('noopener')
      rel.add('noreferrer')
      link.setAttribute('rel', Array.from(rel).join(' '))
    })
  }

  function respectReducedMotion() {
    if (!window.matchMedia || !window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
    document.querySelectorAll('video[data-autoplay]').forEach(function (video) {
      video.controls = true
      video.pause()
    })
    return true
  }

  function setupLazyVideos() {
    var videos = Array.from(document.querySelectorAll('video[data-autoplay]'))
    if (!videos.length || respectReducedMotion()) return

    if (!('IntersectionObserver' in window)) {
      videos.forEach(function (video) {
        video.preload = 'metadata'
        video.play().catch(function () {})
      })
      return
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var video = entry.target
        if (entry.isIntersecting) {
          video.preload = 'metadata'
          video.play().catch(function () {})
        } else {
          video.pause()
        }
      })
    }, { rootMargin: '160px 0px' })

    videos.forEach(function (video) {
      if (video.dataset.lazyVideoReady === 'true') return
      video.dataset.lazyVideoReady = 'true'
      observer.observe(video)
    })
  }

  function enhancePage() {
    CLICKABLES.forEach(function (item) {
      makeKeyboardClickable(item[0], item[1], item[2])
    })
    setActiveNavigation()
    enhanceSearchDialog()
    setupQrSocial()
    setupTagFilter()
    secureExternalLinks()
    setupLazyVideos()
    enhanceScrollableRegions()
    window.setTimeout(enhanceScrollableRegions, 0)
  }

  document.addEventListener('click', function (event) {
    document.querySelectorAll('.qr-social-wrap.is-open').forEach(function (wrapper) {
      if (!wrapper.contains(event.target)) closeQrPopover(wrapper, false)
    })
  })

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return
    document.querySelectorAll('.qr-social-wrap.is-open').forEach(function (wrapper) {
      closeQrPopover(wrapper, true)
    })
  })

  window.addEventListener('resize', function () {
    document.querySelectorAll('.table-wrap').forEach(updateScrollEdges)
    document.querySelectorAll('figure.highlight table').forEach(updateScrollEdges)
  }, { passive: true })

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhancePage, { once: true })
  } else {
    enhancePage()
  }

  document.addEventListener('pjax:complete', enhancePage)
})()
