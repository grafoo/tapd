function init() {
  var httpReq = new XMLHttpRequest();
  httpReq.open('GET', '/play', true);
  httpReq.send();
}
