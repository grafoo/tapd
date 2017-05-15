function init() {
  getRadios();
  getPodcasts();
  updateStreamTitle();
}

function updateStreamTitle() {
  var ws = new WebSocket('ws://' + window.location.host + '/streaminfo');
  ws.onmessage = function(event){
    var streaminfo = JSON.parse(event.data);
    document.getElementById('now-playing').value = streaminfo.title;
  };
}

// deprecated
function pollStreamTitle() {
  id = window.setInterval(getStreamTitle, 1000);
}

// deprecated
function getStreamTitle() {
  window.fetch('/streaminfo').then(function(response){
    return response.json();
  }).then(function(streaminfo){
    document.getElementById('now-playing').value = streaminfo.title;
  });
}

function getRadios() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/radios', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      var radios = document.getElementById('radios');
      for (radio of xhr.response.radios) {
        var newRadio = document.createElement('li');
        var newPlayRadio = document.createElement('a');
        newPlayRadio.href = 'javascript:playradio("' + radio.id + '");';
        newPlayRadio.innerHTML = radio.name;
        newRadio.appendChild(newPlayRadio);
        radios.appendChild(newRadio);
      }
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
      var podcasts = document.getElementById('podcasts');
      for (podcast of xhr.response.podcasts) {
        var newPodcast = document.createElement('div');
        newPodcast.id = "podcast-" + podcast.id;
        var newPodcastName = document.createElement('h1');
        newPodcastName.innerHTML = podcast.title;
        newPodcast.appendChild(newPodcastName);

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

          var newContent = document.createElement('div');
          newContent.style.fontWeight = 'normal';
          newContent.innerHTML = episode.content;
          newEpisode.appendChild(newContent);

          newPodcast.appendChild(newEpisode);
        }

        var newGetAllEpisodes = document.createElement('a');
        newGetAllEpisodes.href = 'javascript:getAllEpisodes(' + podcast.id + ');';
        newGetAllEpisodes.innerHTML = 'LOAD ALL';
        newPodcast.appendChild(newGetAllEpisodes);

        podcasts.appendChild(newPodcast);
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

function playradio(id) {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', '/playradio', true);
  xhr.send('id=' + id);
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

function forward() {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/forward', true);
  xhr.send();
}

function backward() {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/backward', true);
  xhr.send();
}

function toggleMenu() {
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

function toggleRadios() {
  var radios = document.getElementById('radios');
  if (radios.className == 'hidden') {
    radios.className = 'visible';
  } else {
    radios.className = 'hidden';
  }
}

function getAllEpisodes(podcastID) {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/podcast/episodes?id=' + podcastID + '&range=all', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      var oldPodcast = document.getElementById('podcast-' + xhr.response.podcast.id);
      oldPodcast.remove();

      var podcasts = document.getElementById('podcasts');

      var newPodcast = document.createElement('div');
      newPodcast.id = "podcast-" + xhr.response.podcast.id;
      var newPodcastName = document.createElement('h1');
      newPodcastName.innerHTML = xhr.response.podcast.title;
      newPodcast.appendChild(newPodcastName);

      for (episode of xhr.response.podcast.episodes) {
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

        newPodcast.appendChild(newEpisode);
      }

      var newGetAllEpisodes = document.createElement('a');
      newGetAllEpisodes.href = 'javascript:getAllEpisodes(' + xhr.response.podcast.id + ');';
      newGetAllEpisodes.innerHTML = 'LOAD ALL';
      newPodcast.appendChild(newGetAllEpisodes);

      podcasts.appendChild(newPodcast);
    }
  }
  xhr.send();
}
