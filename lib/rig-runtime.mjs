import {
  AUTORIG_AUTO_SKIN_SEGMENTS,
  AUTORIG_R18,
  AUTORIG_SEGMENTS,
  AUTORIG_UAL_HINTS,
  NEUTRAL_BIND_POSE,
  RELAXED_PREVIEW_POSE,
  R11_CORE,
} from '../generated/rig-spec.mjs';

export {
  AUTORIG_AUTO_SKIN_SEGMENTS,
  AUTORIG_R18,
  AUTORIG_SEGMENTS,
  AUTORIG_UAL_HINTS,
  NEUTRAL_BIND_POSE,
  RELAXED_PREVIEW_POSE,
  R11_CORE,
};

const PRESETS = new Map([
  [NEUTRAL_BIND_POSE.id, NEUTRAL_BIND_POSE],
  [RELAXED_PREVIEW_POSE.id, RELAXED_PREVIEW_POSE],
]);

const KNOWN_BASE_NAMES = new Set([
  ...R11_CORE.joints.map(joint => joint.baseName),
  ...AUTORIG_R18.joints.map(joint => joint.baseName),
]);

function assertRig(rig) {
  if (!rig || !Array.isArray(rig.joints)) {
    throw new Error('Expected a rig object with a joints array.');
  }
  return rig;
}

function parseCharacterCount(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
}

function clonePosition(position, fallback = [0, 0, 0]) {
  if (!Array.isArray(position) || position.length < 3) {
    return fallback.slice();
  }

  const values = position.slice(0, 3).map(value => Number(value));
  return values.every(Number.isFinite) ? values : fallback.slice();
}

function normalizeQuaternion(quaternion, fallback = [0, 0, 0, 1]) {
  if (!Array.isArray(quaternion) || quaternion.length < 4) {
    return fallback.slice();
  }

  const values = quaternion.slice(0, 4).map(value => Number(value));
  if (!values.every(Number.isFinite)) {
    return fallback.slice();
  }

  const length = Math.hypot(values[0], values[1], values[2], values[3]);
  if (length === 0) {
    return [0, 0, 0, 1];
  }

  return values.map(value => value / length);
}

function parseJointName(jointName) {
  const match = String(jointName || '').match(/^(.+)_(\d+)$/);
  if (!match || !KNOWN_BASE_NAMES.has(match[1])) {
    return null;
  }

  return {
    baseName: match[1],
    characterIndex: Number.parseInt(match[2], 10),
  };
}

function inferCharacterIndexFromPose(serializedPose) {
  return Object.keys(serializedPose || {}).reduce((currentMax, jointName) => {
    const parsed = parseJointName(jointName);
    return parsed ? Math.max(currentMax, parsed.characterIndex) : currentMax;
  }, -1);
}

function clonePose(pose) {
  const clone = {};
  Object.entries(pose || {}).forEach(([name, transform]) => {
    clone[name] = {
      position: clonePosition(transform?.position),
      quaternion: normalizeQuaternion(transform?.quaternion),
    };
  });
  return clone;
}

function getPreset(presetId) {
  const preset = PRESETS.get(presetId);
  if (!preset) {
    throw new Error(`Unknown rig preset "${presetId}".`);
  }
  return preset;
}

export function getJointNames(rig) {
  return assertRig(rig).joints.map(joint => joint.baseName);
}

export function getJointParents(rig) {
  return Object.fromEntries(assertRig(rig).joints.map(joint => [joint.baseName, joint.parent]));
}

export function getJointName(baseName, characterIndex) {
  return `${baseName}_${characterIndex}`;
}

export function buildDefaultPose(characterCount, rig, preset = 'neutral_bind') {
  const count = parseCharacterCount(characterCount) ?? 0;
  const rigSpec = assertRig(rig);
  const presetData = getPreset(preset);
  const pose = {};

  for (let characterIndex = 0; characterIndex < count; characterIndex += 1) {
    rigSpec.joints.forEach(joint => {
      const transform = presetData.joints[joint.baseName] || {
        position: joint.position,
        quaternion: joint.quaternion,
      };
      pose[getJointName(joint.baseName, characterIndex)] = {
        position: clonePosition(transform.position),
        quaternion: normalizeQuaternion(transform.quaternion),
      };
    });
  }

  return pose;
}

export function inferCharacterCount(assetOrPose) {
  if (!assetOrPose || typeof assetOrPose !== 'object') {
    return 0;
  }

  const explicitCount = parseCharacterCount(assetOrPose?.scene?.characterCount ?? assetOrPose?.characterCount);
  if (explicitCount !== null) {
    return explicitCount;
  }

  if (Array.isArray(assetOrPose?.keyframes)) {
    return assetOrPose.keyframes.reduce((currentMax, frame) => {
      return Math.max(currentMax, inferCharacterIndexFromPose(frame?.pose));
    }, -1) + 1;
  }

  const pose = assetOrPose?.pose && typeof assetOrPose.pose === 'object'
    ? assetOrPose.pose
    : assetOrPose;
  return inferCharacterIndexFromPose(pose) + 1;
}

export function normalizePose(serializedPose, { rig, characterCount, fallbackPose = null } = {}) {
  const rigSpec = assertRig(rig);
  const count = parseCharacterCount(characterCount);
  if (count === null) {
    throw new Error('normalizePose requires an explicit non-negative characterCount.');
  }
  if (count <= 0) {
    return {};
  }

  const neutralFallback = buildDefaultPose(count, rigSpec, 'neutral_bind');
  const pose = {};
  const fallback = fallbackPose && typeof fallbackPose === 'object' ? fallbackPose : null;

  for (let characterIndex = 0; characterIndex < count; characterIndex += 1) {
    rigSpec.joints.forEach(joint => {
      const jointName = getJointName(joint.baseName, characterIndex);
      const fallbackTransform = fallback?.[jointName] || neutralFallback[jointName];
      const sourceTransform = serializedPose?.[jointName];

      pose[jointName] = {
        position: clonePosition(sourceTransform?.position, fallbackTransform.position),
        quaternion: normalizeQuaternion(sourceTransform?.quaternion, fallbackTransform.quaternion),
      };
    });
  }

  return pose;
}

export function normalizeKeyframes(keyframes, { rig, characterCount } = {}) {
  const rigSpec = assertRig(rig);
  const count = parseCharacterCount(characterCount);
  if (count === null) {
    throw new Error('normalizeKeyframes requires an explicit non-negative characterCount.');
  }
  if (!Array.isArray(keyframes)) {
    throw new Error('normalizeKeyframes expects an array of keyframes.');
  }
  if (count <= 0) {
    return [];
  }

  const sortedFrames = keyframes
    .map(frame => ({
      time: Math.max(0, Number.parseFloat(frame?.time) || 0),
      pose: frame?.pose && typeof frame.pose === 'object' ? frame.pose : {},
    }))
    .sort((a, b) => a.time - b.time);

  let rollingPose = buildDefaultPose(count, rigSpec, 'neutral_bind');
  return sortedFrames.map(frame => {
    const pose = normalizePose(frame.pose, {
      rig: rigSpec,
      characterCount: count,
      fallbackPose: rollingPose,
    });
    rollingPose = clonePose(pose);
    return {
      time: frame.time,
      pose,
    };
  });
}
