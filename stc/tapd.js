function init() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/init', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      console.log(xhr.response);
      var podcasts = document.getElementById('podcasts');
      for (podcast of xhr.response.podcasts) {
        var newPodcast = document.createElement('h1');
        newPodcast.innerHTML = podcast.title;
        podcasts.appendChild(newPodcast);

        for (var i=podcast.episodes.length - 1; i>=0; i--) {
          var episode = podcast.episodes[i];

          var newEpisode = document.createElement('div');
          newEpisode.style.fontWeight = 'bold';
          newEpisode.style.paddingTop = '1em';
          newEpisode.innerHTML = episode.title + ' >> ';

          var newPlayEpisode = document.createElement('a');
          newPlayEpisode.href = 'javascript:play("' + episode.stream_uri + '");';
          newPlayEpisode.innerHTML = 'play ';
          newEpisode.appendChild(newPlayEpisode);

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
