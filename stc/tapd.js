function init() {
  getRadios();
  getPodcasts();
}

function getRadios() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/radios', true);
  xhr.onreadystatechange = function() {
    var radios = document.getElementById('radios');
    for (radio of xhr.response.radios) {
      var newRadio = document.createElement('li');
      var newPlayRadio = document.createElement('a');
      newPlayRadio.href = 'javascript:play("' + radio.stream_uri + '");';
      newPlayRadio.innerHTML = radio.name;
      newRadio.appendChild(newPlayRadio);
      radios.appendChild(newRadio);
    }
  }
  xhr.send();
}

function getPodcasts() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/podcasts', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      console.log(xhr.response);
      var podcasts = document.getElementById('podcasts');
      for (podcast of xhr.response.podcasts) {
        var newPodcast = document.createElement('h1');
        newPodcast.innerHTML = podcast.title;
        podcasts.appendChild(newPodcast);

        // for (var i=podcast.episodes.length - 1; i>=0; i--) {
        for (episode of podcast.episodes) {
          var newEpisode = document.createElement('DETAILS');
          var episodeSummary = document.createElement('SUMMARY');
          var episodeTitle = document.createElement('span');
          episodeTitle.innerHTML = episode.title + '  >>' + ' [ ' + episode.duration + ' ] ';
          episodeSummary.appendChild(episodeTitle);
          newEpisode.appendChild(episodeSummary);

          var newPlayEpisode = document.createElement('a');
          newPlayEpisode.href = 'javascript:play("' + episode.stream_uri + '");';
          newPlayEpisode.innerHTML = 'PLAY';
          episodeSummary.appendChild(newPlayEpisode);

          var newDescription = document.createElement('div');
          newDescription.style.fontWeight = 'normal';
          newDescription.innerHTML = episode.description;
          newEpisode.appendChild(newDescription);

          podcasts.appendChild(newEpisode);
        }
      }
    }
  };
  xhr.send();
}

function play(uri) {
  if (uri === undefined) {
    uri = document.getElementById('uri').value;
  }
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/play', true);
  xhr.send('uri=' + uri);
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

function toggleMenu(){
  var menuItems = document.getElementById('menu-items');
  var menuButton = document.getElementById('menu-button');
  if (menuItems.className == 'hidden') {
    menuButton.style.opacity = 1;
    menuButton.innerHTML = "&#8855;";
    menuItems.className = 'visible';
  } else {
    menuButton.style.opacity = 0.1;
    menuButton.innerHTML = "&#8857;";
    menuItems.className = 'hidden';
  }
}

function toggleRadios(){
  var radios = document.getElementById('radios');
  if (radios.className == 'hidden') {
    radios.className = 'visible';
  } else {
    radios.className = 'hidden';
  }
}
