function init() {
  getRadios();
  getPodcasts();
  // updateStreamTitle();
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
        var newRadio = document.createElement('a');
        newRadio.classList.add('collection-item');
        newRadio.href = 'javascript:playradio("' + radio.id + '");';
        newRadio.innerHTML = radio.name + '<i class="material-icons right">&#xe037;</i>';
        radios.appendChild(newRadio);
      }
    }
  }
  xhr.send();
}

function addPodcast(podcastTab, podcastLinks, podcast) {
  var newPodcast = document.createElement('ul');
  newPodcast.classList.add('collapsible');
  newPodcast.setAttribute('data-collapsible', 'accordion');
  newPodcast.id = 'podcast-' + podcast.id;

  var newPodcastLabel = document.createElement('label');
  newPodcastLabel.id = 'podcast-label-' + podcast.id;
  newPodcastLabel.htmlFor = 'podcast-' + podcast.id;
  newPodcastLabel.innerHTML = podcast.title;

  podcastTab.appendChild(newPodcastLabel);

  podcastTab.appendChild(newPodcast);

  var newPodcastLink = document.createElement('a');
  newPodcastLink.classList.add('collection-item');
  newPodcastLink.href = '#podcast-label-' + podcast.id;
  newPodcastLink.innerHTML = '<i class="material-icons left">link</i> ' + podcast.title;
  podcastLinks.appendChild(newPodcastLink);

  for (episode of podcast.episodes) {
    var newEpisode = document.createElement('li');
    var newEpisodeHeader = document.createElement('div');
    newEpisodeHeader.classList.add('collapsible-header');
    newEpisodeHeader.innerHTML = episode.title;
    newEpisode.appendChild(newEpisodeHeader);

    var newEpisodeBody = document.createElement('div');
    newEpisodeBody.classList.add('collapsible-body');

    var newEpisodeBodyHead = document.createElement('div');
    newEpisodeBodyHead.setAttribute('class', 'row');

    if(episode.duration) {
    var newEpisodeDuration = document.createElement('div');
    newEpisodeDuration.innerHTML = '&#x23F2; ' + episode.duration;
    newEpisodeDuration.setAttribute('class', 'col s6');
    newEpisodeBodyHead.appendChild(newEpisodeDuration);
    }

    var newEpisodePlayButton = document.createElement('a')
    newEpisodePlayButton.href = 'javascript:play("' + episode.stream_uri + '");';
    newEpisodePlayButton.innerHTML = 'play';
    newEpisodePlayButton.setAttribute('class', 'btn right');
    newEpisodeBodyHead.appendChild(newEpisodePlayButton);

    newEpisodeBody.appendChild(newEpisodeBodyHead);

    var newEpisodeDescription = document.createElement('div');
    newEpisodeDescription.innerHTML = episode.description;
    newEpisodeBody.appendChild(newEpisodeDescription);
    var newEpisodeContent = document.createElement('div');
    newEpisodeContent.innerHTML = episode.content;
    newEpisodeBody.appendChild(newEpisodeContent);
    newEpisode.appendChild(newEpisodeBody);
    newPodcast.appendChild(newEpisode);
  }

  var newRow = document.createElement('div');
  newRow.setAttribute('class', 'row');
  var newGetAllEpisodesButton = document.createElement('a');
  newGetAllEpisodesButton.href = 'javascript:getAllEpisodes(' + podcast.id + ');';
  newGetAllEpisodesButton.innerHTML = 'load all';
  newGetAllEpisodesButton.setAttribute('class', 'btn right');
  newRow.appendChild(newGetAllEpisodesButton);
  podcastTab.appendChild(newRow);
}

function getPodcasts() {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/podcasts', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      var podcastTab = document.getElementById('podcast-tab');
      var podcastLinks = document.getElementById('podcast-links');
      for (podcast of xhr.response.podcasts) {
        addPodcast(podcastTab, podcastLinks, podcast);
      }
      $('.collapsible').collapsible();
    }
  };
  xhr.send();
}

function getAllEpisodes(podcastID) {
  var xhr = new XMLHttpRequest();
  xhr.responseType = "json";
  xhr.open('GET', '/podcast/episodes?id=' + podcastID + '&range=all', true);
  xhr.onreadystatechange = function() {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      var oldPodcast = document.getElementById('podcast-' + xhr.response.podcast.id);
      oldPodcast.remove();
      var oldPodcastLabel = document.getElementById('podcast-label-' + xhr.response.podcast.id);
      oldPodcastLabel.remove();

      var podcastTab = document.getElementById('podcast-tab');
      var podcastLinks = document.getElementById('podcast-links');

      addPodcast(podcastTab, podcastLinks, xhr.response.podcast);
      $('.collapsible').collapsible();
      $('html,body').animate({scrollTop: $('#podcast-label-' + podcast.id).offset().top}, 600);
    }
  }
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
