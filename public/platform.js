if((location.hash&&location.hash!=='#apps')||new URLSearchParams(location.search).has('next'))location.replace('/social'+location.search+location.hash);
