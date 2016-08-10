function init() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/init', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      console.log(xhr.response);
    }
  };
  xhr.send();
}

function play() {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/play', true);
  xhr.send('uri=' + document.getElementById('uri').value);
}

function pause() {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/pause', true);
  xhr.send();
}

function stop() {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/stop', true);
  xhr.send();
}
