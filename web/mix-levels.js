// Visible gain includes automatic balance; the render API accepts an offset.
const MixLevels = Object.freeze({
 prepare(track) { const base=Number(track.auto_gain_db||0),level=base+Number(track.fader_db||0);return {...track,base_gain_db:base,auto_fader_db:level,fader_db:level}; },
 gain(track) { return track.mute||track.active===false?0:Math.pow(10,Number(track.fader_db||0)/20); },
 offset(track) { return Number(track.fader_db||0)-Number(track.base_gain_db||0); },
});
if(typeof module!=="undefined")module.exports=MixLevels;
