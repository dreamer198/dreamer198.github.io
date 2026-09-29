(function () {
  'use strict'

  // Fade images in once they finish loading instead of letting them pop in.
  // Images that are already decoded (cached) are left alone.
  var images = document.querySelectorAll('#article-container img, #recent-posts img, .home-discovery img')
  images.forEach(function (img) {
    if (img.complete && img.naturalWidth) return
    img.classList.add('img-loading')
    var reveal = function () { img.classList.remove('img-loading') }
    img.addEventListener('load', reveal, { once: true })
    img.addEventListener('error', reveal, { once: true })
  })
})()
