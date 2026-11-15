// Looping previews: respect "reduce motion" and only play while on screen.
(function () {
  var videos = Array.prototype.slice.call(document.querySelectorAll('.tile video'));
  if (!videos.length) return;

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    videos.forEach(function (video) {
      video.removeAttribute('autoplay');
      video.pause();
    });
    return;
  }

  if (!('IntersectionObserver' in window)) return;
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        var played = entry.target.play();
        if (played && played.catch) played.catch(function () {});
      } else {
        entry.target.pause();
      }
    });
  }, { rootMargin: '200px' });
  videos.forEach(function (video) { observer.observe(video); });
})();
