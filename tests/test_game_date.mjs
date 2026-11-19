import test from 'node:test';
import assert from 'node:assert/strict';
import {kickoffLabel,gameCard} from '../web/game-card.js';
test('every game date and time uses Lisbon, including summer midnight and year boundaries',()=>{
 assert.deepEqual(kickoffLabel('2026-11-20T19:30:00Z'),{date:'20/11/2026',time:'19:30',iso:'2026-11-20T19:30:00.000Z'});
 assert.equal(kickoffLabel('2026-07-01T23:30:00Z').date,'02/07/2026');
 assert.equal(kickoffLabel('2026-07-01T23:30:00Z').time,'00:30');
 assert.equal(kickoffLabel('2027-01-01T00:30:00Z').date,'01/01/2027');
});
test('missing, invalid and unzoned times are never presented as an actual fixture date',()=>{
 for(const value of [null,undefined,'bad','2026-11-20T19:30:00'])assert.equal(kickoffLabel(value).iso,'');
});
test('game card preserves the full dated instant in a semantic time element',()=>{
 const html=gameCard({home:'Bayern',away:'Cologne',match:'Bayern vs Cologne',kickoff:'2026-11-20T19:30:00Z',sources:[]});
 assert.match(html,/<time[^>]*datetime="2026-11-20T19:30:00.000Z"/);
 assert.match(html,/20\/11\/2026/);assert.match(html,/Hora de Lisboa/);
});
