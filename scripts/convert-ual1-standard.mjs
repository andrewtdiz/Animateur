#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { AUTORIG_R18, AUTORIG_UAL_HINTS } from '../lib/rig-runtime.mjs';

const repoRoot = process.cwd();
const sourceGlbPath = path.join(repoRoot, 'Animations/universal/UAL1_Standard.glb');
const outputDir = path.join(repoRoot, 'Animations/universal');

const TARGET_RIG = AUTORIG_R18.joints;

const SOURCE_TO_TARGET = {
    Hips: 'pelvis',
    Spine: 'spine_02',
    Neck: 'neck_01',
    Head: 'Head',
    Left_Shoulder: 'clavicle_l',
    Left_Upper_Arm: 'upperarm_l',
    Left_Lower_Arm: 'lowerarm_l',
    Left_Hand: 'hand_l',
    Right_Shoulder: 'clavicle_r',
    Right_Upper_Arm: 'upperarm_r',
    Right_Lower_Arm: 'lowerarm_r',
    Right_Hand: 'hand_r',
    Left_Upper_Leg: 'thigh_l',
    Left_Lower_Leg: 'calf_l',
    Left_Foot: 'foot_l',
    Right_Upper_Leg: 'thigh_r',
    Right_Lower_Leg: 'calf_r',
    Right_Foot: 'foot_r'
};

const DOWN_AXIS = [0, -1, 0];
const DIRECTIONAL_TARGETS = AUTORIG_UAL_HINTS.directionalTargets;
const TARGET_GROUND_SEGMENTS = AUTORIG_UAL_HINTS.groundSegments;

const CHARACTER_COLOR = '#5eead4';
const OUTPUT_PRECISION = 6;

function roundNumber(value) {
    if (!Number.isFinite(value)) return 0;
    return Number.parseFloat(value.toFixed(OUTPUT_PRECISION));
}

function roundVec3(vec) {
    return [roundNumber(vec[0]), roundNumber(vec[1]), roundNumber(vec[2])];
}

function roundQuat(quat) {
    return [roundNumber(quat[0]), roundNumber(quat[1]), roundNumber(quat[2]), roundNumber(quat[3])];
}

function quatNormalize(quat) {
    const [x, y, z, w] = quat;
    const length = Math.hypot(x, y, z, w);
    if (!length) return [0, 0, 0, 1];
    return [x / length, y / length, z / length, w / length];
}

function quatMultiply(a, b) {
    const [ax, ay, az, aw] = a;
    const [bx, by, bz, bw] = b;
    return [
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz
    ];
}

function quatInvert(quat) {
    const [x, y, z, w] = quat;
    const dot = x * x + y * y + z * z + w * w;
    if (!dot) return [0, 0, 0, 1];
    const inv = 1 / dot;
    return [-x * inv, -y * inv, -z * inv, w * inv];
}

function quatSlerp(a, b, t) {
    let [ax, ay, az, aw] = quatNormalize(a);
    let [bx, by, bz, bw] = quatNormalize(b);
    let cosTheta = ax * bx + ay * by + az * bz + aw * bw;

    if (cosTheta < 0) {
        cosTheta = -cosTheta;
        bx = -bx;
        by = -by;
        bz = -bz;
        bw = -bw;
    }

    if (cosTheta > 0.9995) {
        return quatNormalize([
            ax + t * (bx - ax),
            ay + t * (by - ay),
            az + t * (bz - az),
            aw + t * (bw - aw)
        ]);
    }

    const theta = Math.acos(Math.min(1, Math.max(-1, cosTheta)));
    const sinTheta = Math.sin(theta);
    const scaleA = Math.sin((1 - t) * theta) / sinTheta;
    const scaleB = Math.sin(t * theta) / sinTheta;
    return [
        ax * scaleA + bx * scaleB,
        ay * scaleA + by * scaleB,
        az * scaleA + bz * scaleB,
        aw * scaleA + bw * scaleB
    ];
}

function quatRotateVec(quat, vec) {
    const [x, y, z, w] = quatNormalize(quat);
    const vx = vec[0];
    const vy = vec[1];
    const vz = vec[2];

    const uvx = y * vz - z * vy;
    const uvy = z * vx - x * vz;
    const uvz = x * vy - y * vx;

    const uuvx = y * uvz - z * uvy;
    const uuvy = z * uvx - x * uvz;
    const uuvz = x * uvy - y * uvx;

    const tw = 2 * w;
    return [
        vx + 2 * (w * uvx + uuvx),
        vy + 2 * (w * uvy + uuvy),
        vz + 2 * (w * uvz + uuvz)
    ];
}

function vec3Add(a, b) {
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

function vec3Sub(a, b) {
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function vec3Scale(vec, scalar) {
    return [vec[0] * scalar, vec[1] * scalar, vec[2] * scalar];
}

function vec3Multiply(a, b) {
    return [a[0] * b[0], a[1] * b[1], a[2] * b[2]];
}

function vec3Dot(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function vec3Cross(a, b) {
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    ];
}

function vec3Normalize(vec) {
    const length = Math.hypot(vec[0], vec[1], vec[2]);
    if (!length) return null;
    return [vec[0] / length, vec[1] / length, vec[2] / length];
}

function quatFromUnitVectors(fromVec, toVec) {
    const from = vec3Normalize(fromVec);
    const to = vec3Normalize(toVec);
    if (!from || !to) return [0, 0, 0, 1];

    let dot = vec3Dot(from, to) + 1;
    let quaternion;

    if (dot < 1e-6) {
        if (Math.abs(from[0]) > Math.abs(from[2])) {
            quaternion = [-from[1], from[0], 0, 0];
        } else {
            quaternion = [0, -from[2], from[1], 0];
        }
    } else {
        const cross = vec3Cross(from, to);
        quaternion = [cross[0], cross[1], cross[2], dot];
    }

    return quatNormalize(quaternion);
}

function parseGlb(buffer) {
    if (buffer.toString('utf8', 0, 4) !== 'glTF') {
        throw new Error('Source file is not a GLB.');
    }

    const version = buffer.readUInt32LE(4);
    if (version !== 2) {
        throw new Error(`Unsupported GLB version ${version}.`);
    }

    const length = buffer.readUInt32LE(8);
    if (length !== buffer.length) {
        throw new Error('GLB length header does not match file size.');
    }

    let offset = 12;
    let json = null;
    let bin = null;

    while (offset < buffer.length) {
        const chunkLength = buffer.readUInt32LE(offset);
        offset += 4;
        const chunkType = buffer.toString('ascii', offset, offset + 4);
        offset += 4;
        const chunk = buffer.slice(offset, offset + chunkLength);
        offset += chunkLength;

        if (chunkType === 'JSON') {
            json = JSON.parse(chunk.toString('utf8').replace(/\0+$/, ''));
        } else if (chunkType === 'BIN\0') {
            bin = chunk;
        }
    }

    if (!json || !bin) {
        throw new Error('GLB is missing JSON or BIN chunks.');
    }

    return { json, bin };
}

function getAccessorValues(gltf, bin, accessorIndex) {
    const accessor = gltf.accessors[accessorIndex];
    const bufferView = gltf.bufferViews[accessor.bufferView];
    const componentSize = {
        5120: 1,
        5121: 1,
        5122: 2,
        5123: 2,
        5125: 4,
        5126: 4
    }[accessor.componentType];

    const componentReader = {
        5120: (buffer, offset) => buffer.readInt8(offset),
        5121: (buffer, offset) => buffer.readUInt8(offset),
        5122: (buffer, offset) => buffer.readInt16LE(offset),
        5123: (buffer, offset) => buffer.readUInt16LE(offset),
        5125: (buffer, offset) => buffer.readUInt32LE(offset),
        5126: (buffer, offset) => buffer.readFloatLE(offset)
    }[accessor.componentType];

    if (!componentSize || !componentReader) {
        throw new Error(`Unsupported accessor component type ${accessor.componentType}.`);
    }

    const numComponents = {
        SCALAR: 1,
        VEC2: 2,
        VEC3: 3,
        VEC4: 4,
        MAT2: 4,
        MAT3: 9,
        MAT4: 16
    }[accessor.type];

    if (!numComponents) {
        throw new Error(`Unsupported accessor type ${accessor.type}.`);
    }

    const byteOffset = (bufferView.byteOffset || 0) + (accessor.byteOffset || 0);
    const stride = bufferView.byteStride || (numComponents * componentSize);
    const values = [];

    for (let index = 0; index < accessor.count; index += 1) {
        const base = byteOffset + index * stride;
        const entry = [];
        for (let component = 0; component < numComponents; component += 1) {
            entry.push(componentReader(bin, base + component * componentSize));
        }
        values.push(numComponents === 1 ? entry[0] : entry);
    }

    return values;
}

function buildNodeGraph(gltf) {
    const parentByNode = new Array(gltf.nodes.length).fill(null);
    gltf.nodes.forEach((node, nodeIndex) => {
        (node.children || []).forEach(childIndex => {
            parentByNode[childIndex] = nodeIndex;
        });
    });

    const rootNodes = [];
    parentByNode.forEach((parent, nodeIndex) => {
        if (parent === null) rootNodes.push(nodeIndex);
    });

    return { parentByNode, rootNodes };
}

function buildLocalTransform(node, fallback = null) {
    const position = Array.isArray(node.translation) ? node.translation.slice(0, 3).map(Number) : fallback?.position?.slice() || [0, 0, 0];
    const rotation = Array.isArray(node.rotation) ? quatNormalize(node.rotation.slice(0, 4).map(Number)) : fallback?.quaternion?.slice() || [0, 0, 0, 1];
    const scale = Array.isArray(node.scale) ? node.scale.slice(0, 3).map(Number) : fallback?.scale?.slice() || [1, 1, 1];
    return { position, quaternion: rotation, scale };
}

function interpolateScalar(a, b, t) {
    return a + (b - a) * t;
}

function interpolateVec3(a, b, t) {
    return [
        interpolateScalar(a[0], b[0], t),
        interpolateScalar(a[1], b[1], t),
        interpolateScalar(a[2], b[2], t)
    ];
}

function sampleTrack(track, time) {
    const { times, values, interpolation, type } = track;
    if (!times.length) return null;
    if (time <= times[0]) return values[0].slice ? values[0].slice() : values[0];
    if (time >= times[times.length - 1]) {
        const last = values[values.length - 1];
        return last.slice ? last.slice() : last;
    }

    let upperIndex = 1;
    while (upperIndex < times.length && times[upperIndex] < time) upperIndex += 1;
    const lowerIndex = upperIndex - 1;
    const t0 = times[lowerIndex];
    const t1 = times[upperIndex];
    const alpha = t1 === t0 ? 0 : (time - t0) / (t1 - t0);
    const lower = values[lowerIndex];
    const upper = values[upperIndex];

    if (interpolation === 'STEP') {
        return lower.slice ? lower.slice() : lower;
    }

    if (interpolation === 'CUBICSPLINE') {
        throw new Error('Cubic spline interpolation is not supported by this converter.');
    }

    if (type === 'rotation') {
        return quatSlerp(lower, upper, alpha);
    }

    return type === 'translation' || type === 'scale'
        ? interpolateVec3(lower, upper, alpha)
        : interpolateScalar(lower, upper, alpha);
}

function buildClipTracks(gltf, bin, animation) {
    const tracksByNode = new Map();

    animation.samplers.forEach((sampler, samplerIndex) => {
        const channel = animation.channels.find(entry => entry.sampler === samplerIndex);
        if (!channel) return;

        const nodeIndex = channel.target.node;
        const pathName = channel.target.path;
        const interpolation = sampler.interpolation || 'LINEAR';
        const times = getAccessorValues(gltf, bin, sampler.input).map(Number);
        const rawValues = getAccessorValues(gltf, bin, sampler.output);
        const type = pathName;

        let values;
        if (pathName === 'rotation') {
            values = rawValues.map(entry => quatNormalize(entry.map(Number)));
        } else if (pathName === 'translation' || pathName === 'scale') {
            values = rawValues.map(entry => entry.map(Number));
        } else {
            values = rawValues.map(Number);
        }

        if (!tracksByNode.has(nodeIndex)) {
            tracksByNode.set(nodeIndex, {});
        }

        tracksByNode.get(nodeIndex)[pathName] = {
            times,
            values,
            interpolation,
            type
        };
    });

    return tracksByNode;
}

function gatherUniqueTimes(animation) {
    const times = new Map();
    animation.samplers.forEach(sampler => {
        const input = sampler._cachedTimes;
        if (!Array.isArray(input)) return;
        input.forEach(time => times.set(time.toFixed(6), time));
    });
    return Array.from(times.values()).sort((a, b) => a - b);
}

function computeWorldTransforms(parentByNode, localTransforms) {
    const world = new Array(localTransforms.length);
    const childrenByNode = new Map();
    parentByNode.forEach((parent, nodeIndex) => {
        if (parent === null) return;
        if (!childrenByNode.has(parent)) childrenByNode.set(parent, []);
        childrenByNode.get(parent).push(nodeIndex);
    });

    function visit(nodeIndex, parentWorld) {
        const local = localTransforms[nodeIndex];
        const worldQuat = parentWorld
            ? quatNormalize(quatMultiply(parentWorld.quaternion, local.quaternion))
            : quatNormalize(local.quaternion);
        const worldScale = parentWorld
            ? vec3Multiply(parentWorld.scale, local.scale)
            : local.scale.slice();
        const rotatedPosition = parentWorld
            ? quatRotateVec(parentWorld.quaternion, vec3Multiply(local.position, parentWorld.scale))
            : local.position.slice();
        const worldPos = parentWorld
            ? vec3Add(parentWorld.position, rotatedPosition)
            : local.position.slice();

        world[nodeIndex] = {
            position: worldPos,
            quaternion: worldQuat,
            scale: worldScale
        };

        (childrenByNode.get(nodeIndex) || []).forEach(childIndex => visit(childIndex, world[nodeIndex]));
    }

    parentByNode.forEach((parent, nodeIndex) => {
        if (parent === null) visit(nodeIndex, null);
    });

    return world;
}

function buildTargetTransformsForRest() {
    const parentByTarget = new Map();
    TARGET_RIG.forEach(joint => parentByTarget.set(joint.baseName, joint.parent));

    const localByTarget = new Map();
    TARGET_RIG.forEach(joint => {
        localByTarget.set(joint.baseName, {
            position: joint.position.slice(),
            quaternion: joint.quaternion.slice(),
            scale: [1, 1, 1]
        });
    });

    const worldByTarget = new Map();

    function visit(name) {
        if (worldByTarget.has(name)) return worldByTarget.get(name);
        const joint = TARGET_RIG.find(entry => entry.baseName === name);
        if (!joint) throw new Error(`Unknown target joint ${name}.`);
        const parentName = parentByTarget.get(name);
        const local = localByTarget.get(name);
        const parentWorld = parentName ? visit(parentName) : null;
        const world = parentWorld
            ? {
                position: vec3Add(parentWorld.position, quatRotateVec(parentWorld.quaternion, vec3Multiply(local.position, parentWorld.scale))),
                quaternion: quatNormalize(quatMultiply(parentWorld.quaternion, local.quaternion)),
                scale: vec3Multiply(parentWorld.scale, local.scale)
            }
            : {
                position: local.position.slice(),
                quaternion: quatNormalize(local.quaternion.slice()),
                scale: local.scale.slice()
            };
        worldByTarget.set(name, world);
        return world;
    }

    TARGET_RIG.forEach(joint => visit(joint.baseName));
    return { localByTarget, worldByTarget, parentByTarget };
}

function createLocalPoseFromWorld(worldByTarget, parentByTarget, targetName, desiredWorld, localPositionOverride = null) {
    const parentName = parentByTarget.get(targetName);
    const parentWorld = parentName ? worldByTarget.get(parentName) : null;
    const localPosition = localPositionOverride || [0, 0, 0];

    if (!parentWorld) {
        return {
            position: localPosition.slice(),
            quaternion: quatNormalize(desiredWorld.quaternion.slice())
        };
    }

    const relativeQuaternion = quatMultiply(quatInvert(parentWorld.quaternion), desiredWorld.quaternion);
    return {
        position: localPosition.slice(),
        quaternion: quatNormalize(relativeQuaternion)
    };
}

function applyLocalPoseToWorld(worldByTarget, parentByTarget, targetName, localPose) {
    const parentName = parentByTarget.get(targetName);
    const parentWorld = parentName ? worldByTarget.get(parentName) : null;

    const worldPosition = parentWorld
        ? vec3Add(parentWorld.position, quatRotateVec(parentWorld.quaternion, localPose.position))
        : localPose.position.slice();
    const worldQuaternion = parentWorld
        ? quatNormalize(quatMultiply(parentWorld.quaternion, localPose.quaternion))
        : quatNormalize(localPose.quaternion.slice());

    const worldTransform = {
        position: worldPosition,
        quaternion: worldQuaternion,
        scale: [1, 1, 1]
    };

    worldByTarget.set(targetName, worldTransform);
    return worldTransform;
}

function getSourceGroundHeight(currentWorld, sourceNodeIndices) {
    let minY = Number.POSITIVE_INFINITY;
    sourceNodeIndices.forEach(nodeIndex => {
        const worldPose = currentWorld[nodeIndex];
        if (!worldPose) return;
        minY = Math.min(minY, worldPose.position[1]);
    });
    return Number.isFinite(minY) ? minY : 0;
}

function getTargetGroundHeight(worldByTarget) {
    let minY = Number.POSITIVE_INFINITY;

    TARGET_GROUND_SEGMENTS.forEach(segment => {
        const start = worldByTarget.get(segment.start);
        const end = worldByTarget.get(segment.end);
        if (!start || !end) return;
        minY = Math.min(
            minY,
            start.position[1] - segment.radius,
            end.position[1] - segment.radius
        );
    });

    return Number.isFinite(minY) ? minY : 0;
}

function sanitizeFileName(name) {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'clip';
}

async function readJsonIfExists(filePath) {
    try {
        const raw = await readFile(filePath, 'utf8');
        return JSON.parse(raw);
    } catch (error) {
        if (error?.code === 'ENOENT') {
            return null;
        }
        throw error;
    }
}

function withoutTimestamp(value, fieldName) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return value;
    }
    const clone = { ...value };
    delete clone[fieldName];
    return clone;
}

function preserveTimestamp(nextValue, existingValue, fieldName, fallbackTimestamp) {
    if (existingValue && JSON.stringify(withoutTimestamp(existingValue, fieldName)) === JSON.stringify(withoutTimestamp(nextValue, fieldName))) {
        return existingValue[fieldName] || fallbackTimestamp;
    }
    return fallbackTimestamp;
}

function buildTimeList(gltf, bin, animation) {
    const times = new Map();
    animation.samplers.forEach(sampler => {
        const inputTimes = getAccessorValues(gltf, bin, sampler.input).map(Number);
        inputTimes.forEach(time => times.set(time.toFixed(6), time));
    });
    return Array.from(times.values()).sort((a, b) => a - b);
}

function buildLocalSamplesAtTime(gltf, bin, animation, time) {
    const tracks = buildClipTracks(gltf, bin, animation);
    const locals = gltf.nodes.map(node => buildLocalTransform(node));

    tracks.forEach((paths, nodeIndex) => {
        const local = locals[nodeIndex];
        if (paths.translation) local.position = sampleTrack(paths.translation, time).map(Number);
        if (paths.rotation) local.quaternion = quatNormalize(sampleTrack(paths.rotation, time).map(Number));
        if (paths.scale) local.scale = sampleTrack(paths.scale, time).map(Number);
    });

    return locals;
}

function computeSourceWorldAtTime(gltf, parentByNode, animation, time) {
    const localSamples = buildLocalSamplesAtTime(gltf, null, animation, time);
    return computeWorldTransforms(parentByNode, localSamples);
}

function buildAnimationAsset({
    timeSamples,
    sourceRestLocals,
    sourceRestWorld,
    sourceWorldSamplesByTime,
    sourceLocalSamplesByTime,
    targetRest,
    animationName,
    sourceNodeIndexByName,
    mappedSourceNodeIndices
}) {
    const keyframes = [];

    timeSamples.forEach(time => {
        const pose = {};
        const timeKey = time.toFixed(6);
        const currentLocals = sourceLocalSamplesByTime.get(time.toFixed(6));
        if (!currentLocals) {
            throw new Error(`Missing sampled pose for ${animationName} at ${time}.`);
        }
        const currentWorld = sourceWorldSamplesByTime.get(timeKey)?.world;
        if (!currentWorld) {
            throw new Error(`Missing sampled world pose for ${animationName} at ${time}.`);
        }

        const targetWorldPose = new Map();

        TARGET_RIG.forEach(joint => {
            const sourceNodeName = SOURCE_TO_TARGET[joint.baseName];
            const sourceNodeIndex = sourceNodeIndexByName.get(sourceNodeName);
            if (typeof sourceNodeIndex !== 'number') {
                throw new Error(`Missing source node for ${joint.baseName}.`);
            }

            const currentSourceLocal = currentLocals[sourceNodeIndex];
            const restSourceLocal = sourceRestLocals[sourceNodeIndex];
            const localQuaternion = quatMultiply(quatInvert(restSourceLocal.quaternion), currentSourceLocal.quaternion);

            if (joint.baseName === 'Hips') {
                const currentSourceWorld = currentWorld[sourceNodeIndex];
                const restSourceWorldPose = sourceRestWorld.world[sourceNodeIndex];
                const sourceDeltaPos = currentSourceWorld && restSourceWorldPose
                    ? vec3Sub(currentSourceWorld.position, restSourceWorldPose.position)
                    : vec3Sub(currentSourceLocal.position, restSourceLocal.position);
                const localPosition = [
                    targetRest.localByTarget.get('Hips').position[0] + sourceDeltaPos[0],
                    0,
                    targetRest.localByTarget.get('Hips').position[2] + sourceDeltaPos[2]
                ];
                const localPose = {
                    position: roundVec3(localPosition),
                    quaternion: roundQuat(quatNormalize(localQuaternion))
                };
                pose.Hips_0 = localPose;
                applyLocalPoseToWorld(targetWorldPose, targetRest.parentByTarget, joint.baseName, {
                    position: localPosition,
                    quaternion: quatNormalize(localQuaternion)
                });
                return;
            }

            let resolvedLocalQuaternion = quatNormalize(localQuaternion);
            const directionalTargetName = DIRECTIONAL_TARGETS[joint.baseName];
            if (directionalTargetName) {
                const sourceChildNodeName = SOURCE_TO_TARGET[directionalTargetName];
                const sourceChildNodeIndex = sourceNodeIndexByName.get(sourceChildNodeName);
                if (typeof sourceChildNodeIndex !== 'number') {
                    throw new Error(`Missing source child node for ${joint.baseName}.`);
                }

                const sourceDirection = vec3Normalize(vec3Sub(
                    currentWorld[sourceChildNodeIndex].position,
                    currentWorld[sourceNodeIndex].position
                ));

                if (sourceDirection) {
                    const desiredWorldQuaternion = quatFromUnitVectors(DOWN_AXIS, sourceDirection);
                    resolvedLocalQuaternion = createLocalPoseFromWorld(
                        targetWorldPose,
                        targetRest.parentByTarget,
                        joint.baseName,
                        { quaternion: desiredWorldQuaternion },
                        targetRest.localByTarget.get(joint.baseName).position
                    ).quaternion;
                }
            }

            const localPose = {
                position: roundVec3(targetRest.localByTarget.get(joint.baseName).position),
                quaternion: roundQuat(resolvedLocalQuaternion)
            };
            pose[`${joint.baseName}_0`] = localPose;
            applyLocalPoseToWorld(targetWorldPose, targetRest.parentByTarget, joint.baseName, {
                position: targetRest.localByTarget.get(joint.baseName).position,
                quaternion: resolvedLocalQuaternion
            });
        });

        const sourceGroundHeight = getSourceGroundHeight(currentWorld, mappedSourceNodeIndices);
        const targetGroundHeight = getTargetGroundHeight(targetWorldPose);
        pose.Hips_0.position[1] = roundNumber(sourceGroundHeight - targetGroundHeight);

        keyframes.push({
            time: roundNumber(time),
            pose
        });
    });

    return {
        format: 'fast-poser-asset',
        version: 1,
        type: 'animation',
        name: animationName,
        savedAt: new Date().toISOString(),
        scene: {
            characterCount: 1,
            characterColors: [CHARACTER_COLOR]
        },
        playbackSpeed: 1,
        effects: null,
        keyframes
    };
}

async function main() {
    const sourceBuffer = await readFile(sourceGlbPath);
    const { json: gltf, bin } = parseGlb(sourceBuffer);
    const { parentByNode } = buildNodeGraph(gltf);
    const sourceNodeIndexByName = new Map();
    gltf.nodes.forEach((node, index) => {
        if (node.name) sourceNodeIndexByName.set(node.name, index);
    });
    const mappedSourceNodeIndices = TARGET_RIG.map(joint => sourceNodeIndexByName.get(SOURCE_TO_TARGET[joint.baseName]))
        .filter(nodeIndex => typeof nodeIndex === 'number');

    const restAnimation = gltf.animations.find(animation => animation.name === 'A_TPose') || gltf.animations[0];
    if (!restAnimation) {
        throw new Error('No animation clips found in the GLB.');
    }

    const restTracks = buildClipTracks(gltf, bin, restAnimation);
    const restTimes = buildTimeList(gltf, bin, restAnimation);
    const restTime = restTimes[0] ?? 0;
    const restLocals = gltf.nodes.map(node => buildLocalTransform(node));

    restTracks.forEach((paths, nodeIndex) => {
        const local = restLocals[nodeIndex];
        if (paths.translation) local.position = sampleTrack(paths.translation, restTime).map(Number);
        if (paths.rotation) local.quaternion = quatNormalize(sampleTrack(paths.rotation, restTime).map(Number));
        if (paths.scale) local.scale = sampleTrack(paths.scale, restTime).map(Number);
    });

    const sourceRestWorld = {
        world: computeWorldTransforms(parentByNode, restLocals)
    };
    const targetRest = buildTargetTransformsForRest();

    await mkdir(outputDir, { recursive: true });
    const buildTimestamp = new Date().toISOString();
    const manifestPath = path.join(outputDir, 'manifest.json');
    const existingManifest = await readJsonIfExists(manifestPath);

    const manifest = [];
    for (const animation of gltf.animations) {
        const times = buildTimeList(gltf, bin, animation);
        const animationTracks = buildClipTracks(gltf, bin, animation);
        const sourceLocalSamplesByTime = new Map();
        const sourceWorldSamplesByTime = new Map();

        for (const time of times) {
            const locals = gltf.nodes.map(node => buildLocalTransform(node));
            animationTracks.forEach((paths, nodeIndex) => {
                const local = locals[nodeIndex];
                if (paths.translation) local.position = sampleTrack(paths.translation, time).map(Number);
                if (paths.rotation) local.quaternion = quatNormalize(sampleTrack(paths.rotation, time).map(Number));
                if (paths.scale) local.scale = sampleTrack(paths.scale, time).map(Number);
            });
            sourceLocalSamplesByTime.set(time.toFixed(6), locals);
            sourceWorldSamplesByTime.set(time.toFixed(6), {
                world: computeWorldTransforms(parentByNode, locals)
            });
        }

        const asset = buildAnimationAsset({
            timeSamples: times,
            sourceRestLocals: restLocals,
            sourceRestWorld,
            sourceWorldSamplesByTime,
            sourceLocalSamplesByTime,
            targetRest,
            animationName: animation.name,
            sourceNodeIndexByName,
            mappedSourceNodeIndices
        });

        const fileName = `${sanitizeFileName(animation.name)}.animation.json`;
        const filePath = path.join(outputDir, fileName);
        const existingAsset = await readJsonIfExists(filePath);
        asset.savedAt = preserveTimestamp(asset, existingAsset, 'savedAt', buildTimestamp);
        await writeFile(filePath, `${JSON.stringify(asset, null, 2)}\n`, 'utf8');
        manifest.push({
            file: fileName,
            name: animation.name,
            duration: roundNumber(times[times.length - 1] ?? 0),
            keyframes: asset.keyframes.length
        });
    }

    const nextManifest = {
        source: 'Animations/universal/UAL1_Standard.glb',
        generatedAt: buildTimestamp,
        characterCount: 1,
        rig: TARGET_RIG.map(joint => joint.baseName),
        clips: manifest
    };
    nextManifest.generatedAt = preserveTimestamp(nextManifest, existingManifest, 'generatedAt', buildTimestamp);

    await writeFile(manifestPath, `${JSON.stringify(nextManifest, null, 2)}\n`, 'utf8');

    console.log(`Wrote ${manifest.length} animation files to ${outputDir}`);
}

main().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
