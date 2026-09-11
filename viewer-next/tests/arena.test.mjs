import assert from 'node:assert/strict';
import { moveLoss, scoreLabel } from '../src/lib/arena.ts';

assert.equal(moveLoss({cp_white:80}, {cp_white:-20}, 'white'), 100);
assert.equal(moveLoss({cp_white:80}, {cp_white:160}, 'black'), 80);
assert.equal(moveLoss({cp_white:80}, {cp_white:160}, 'white'), 0);
assert.equal(moveLoss({cp_white:null,mate_white:3}, {cp_white:160}, 'black'), null);
assert.equal(moveLoss(undefined, {cp_white:160}, 'black'), null);
assert.equal(scoreLabel({cp_white:0,mate_white:null}), '0.00');
assert.equal(scoreLabel({cp_white:null,mate_white:0}), 'Mate');
assert.equal(scoreLabel({cp_white:null,mate_white:-3}), '−M3');
assert.equal(scoreLabel({cp_white:38,mate_white:null}), '+0.38');
