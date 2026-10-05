import sdk, {
    BinarySensor, Camera, Device, DeviceProvider, FFmpegInput, Intercom, MediaObject,
    MediaStreamOptions, PictureOptions, ResponseMediaStreamOptions,
    ScryptedDeviceBase, ScryptedDeviceType, ScryptedInterface,
    ScryptedMimeTypes, Setting, Settings, SettingValue, VideoCamera,
} from '@scrypted/sdk';
import { ChildProcess, spawn } from 'child_process';
import { createServer, Server } from 'http';
import { connect, Socket } from 'net';

const { deviceManager, mediaManager } = sdk;
const DEVICE_ID = 'neolight-door';
const DEFAULT_VIDEO = 'rtsp://127.0.0.1:8556/neolight_door_with_audio';
const DEFAULT_TALK_PORT = 38556;
const DEFAULT_RING_PORT = 38765;

class NeoLightCamera extends ScryptedDeviceBase implements BinarySensor, Camera, VideoCamera, Intercom {
    private ffmpeg?: ChildProcess;
    private talkSocket?: Socket;
    private microphoneBytes = 0;
    private ringTimer?: NodeJS.Timeout;
    private snapshotProcess?: ChildProcess;
    private snapshotRetry?: NodeJS.Timeout;
    private snapshotHealth?: NodeJS.Timeout;
    private snapshotBytes = Buffer.alloc(0);
    private snapshot?: Buffer;
    private snapshotAt = 0;
    private snapshotWaiters: Array<(image: Buffer) => void> = [];
    private released = false;

    constructor(private plugin: NeoLightPlugin) {
        super(DEVICE_ID);
        this.binaryState = false;
        void this.startSnapshotReader();
        this.snapshotHealth = setInterval(() => {
            if (this.snapshotProcess && Date.now() - Math.max(this.snapshotAt, this.snapshotStartedAt) > 15_000)
                this.snapshotProcess.kill('SIGKILL');
        }, 5000);
    }

    private snapshotStartedAt = Date.now();

    private async startSnapshotReader(): Promise<void> {
        if (this.released)
            return;
        const ffmpeg = await mediaManager.getFFmpegPath();
        if (this.released)
            return;
        const child = spawn(ffmpeg, [
            '-loglevel', 'error', '-rtsp_transport', 'tcp', '-i', this.plugin.videoUrl,
            '-an', '-vf', 'fps=1,scale=640:-2', '-q:v', '5',
            '-f', 'image2pipe', '-vcodec', 'mjpeg', 'pipe:1',
        ]);
        this.snapshotStartedAt = Date.now();
        this.snapshotProcess = child;
        child.stdout.on('data', (chunk: Buffer) => this.readSnapshotBytes(chunk));
        child.on('error', error => this.console.error('NeoLight snapshot reader failed', error));
        child.on('close', () => {
            if (this.snapshotProcess === child)
                this.snapshotProcess = undefined;
            if (!this.released)
                this.snapshotRetry = setTimeout(() => void this.startSnapshotReader(), 1000);
        });
    }

    private readSnapshotBytes(chunk: Buffer): void {
        this.snapshotBytes = Buffer.concat([this.snapshotBytes, chunk]);
        if (this.snapshotBytes.length > 4_000_000) {
            this.snapshotBytes = Buffer.alloc(0);
            return;
        }
        while (true) {
            const start = this.snapshotBytes.indexOf(Buffer.from([0xff, 0xd8]));
            if (start < 0) {
                this.snapshotBytes = Buffer.alloc(0);
                return;
            }
            const end = this.snapshotBytes.indexOf(Buffer.from([0xff, 0xd9]), start + 2);
            if (end < 0) {
                this.snapshotBytes = this.snapshotBytes.subarray(start);
                return;
            }
            this.snapshot = Buffer.from(this.snapshotBytes.subarray(start, end + 2));
            this.snapshotAt = Date.now();
            this.snapshotBytes = this.snapshotBytes.subarray(end + 2);
            for (const waiter of this.snapshotWaiters.splice(0))
                waiter(this.snapshot);
        }
    }

    release(): void {
        this.released = true;
        if (this.snapshotRetry)
            clearTimeout(this.snapshotRetry);
        if (this.snapshotHealth)
            clearInterval(this.snapshotHealth);
        this.snapshotProcess?.kill('SIGTERM');
        if (this.ringTimer)
            clearTimeout(this.ringTimer);
    }

    ring(): void {
        if (this.ringTimer)
            clearTimeout(this.ringTimer);
        this.binaryState = true;
        this.ringTimer = setTimeout(() => {
            this.binaryState = false;
            this.ringTimer = undefined;
        }, 3000);
    }

    async getVideoStream(_options?: MediaStreamOptions): Promise<MediaObject> {
        const url = this.plugin.videoUrl;
        const input: FFmpegInput = {
            url,
            container: 'rtsp',
            mediaStreamOptions: (await this.getVideoStreamOptions())[0],
            inputArguments: ['-rtsp_transport', 'tcp', '-i', url],
            h264EncoderArguments: ['-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency', '-pix_fmt', 'yuv420p', '-g', '50', '-bf', '0'],
        };
        return mediaManager.createMediaObject(Buffer.from(JSON.stringify(input)), ScryptedMimeTypes.FFmpegInput);
    }

    async getVideoStreamOptions(): Promise<ResponseMediaStreamOptions[]> {
        return [{ id: 'door', name: 'Entrance', container: 'rtsp', video: { codec: 'h264', width: 1280, height: 720 }, audio: { codec: 'pcma', sampleRate: 8000 } }];
    }

    async getPictureOptions(): Promise<PictureOptions[]> {
        return [];
    }

    async takePicture(_options?: PictureOptions): Promise<MediaObject> {
        let image = this.snapshot;
        if (!image || Date.now() - this.snapshotAt > 30_000) {
            image = await new Promise<Buffer>((resolve, reject) => {
                const waiter = (frame: Buffer) => { clearTimeout(timeout); resolve(frame); };
                const timeout = setTimeout(() => {
                    this.snapshotWaiters = this.snapshotWaiters.filter(item => item !== waiter);
                    reject(new Error('NeoLight snapshot reader timed out'));
                }, 8000);
                this.snapshotWaiters.push(waiter);
            });
        }
        return mediaManager.createMediaObject(image, 'image/jpeg');
    }

    async startIntercom(media: MediaObject): Promise<void> {
        await this.stopIntercom();
        const input = JSON.parse((await mediaManager.convertMediaObjectToBuffer(media, ScryptedMimeTypes.FFmpegInput)).toString()) as FFmpegInput;
        const socket = connect(this.plugin.talkPort, '127.0.0.1');
        try {
            await new Promise<void>((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error('NeoLight P2P talk connection timed out')), 3000);
                socket.once('connect', () => { clearTimeout(timeout); resolve(); });
                socket.once('error', error => { clearTimeout(timeout); reject(error); });
            });
        }
        catch (error) {
            socket.destroy();
            throw error;
        }
        socket.setNoDelay(true);
        this.talkSocket = socket;
        this.microphoneBytes = 0;
        socket.on('error', error => {
            this.console.error('NeoLight P2P talk socket failed', error);
            void this.stopIntercom();
        });
        socket.on('close', () => void this.stopIntercom());
        const ffmpeg = await mediaManager.getFFmpegPath();
        const child = spawn(ffmpeg, [
            '-loglevel', 'error', ...(input.inputArguments || ['-i', input.url!]),
            '-vn', '-ac', '1', '-ar', '8000', '-acodec', 'pcm_mulaw',
            '-f', 'mulaw', 'pipe:1',
        ]);
        this.ffmpeg = child;
        child.stdout.on('data', (chunk: Buffer) => {
            if (this.talkSocket !== socket || socket.destroyed)
                return;
            this.microphoneBytes += chunk.length;
            if (!socket.write(chunk))
                child.stdout.pause();
        });
        socket.on('drain', () => child.stdout.resume());
        child.on('error', error => this.console.error('NeoLight microphone encoding failed', error));
        child.on('close', () => void this.stopIntercom());
    }

    async stopIntercom(): Promise<void> {
        const child = this.ffmpeg;
        this.ffmpeg = undefined;
        child?.kill('SIGTERM');
        const socket = this.talkSocket;
        this.talkSocket = undefined;
        socket?.destroy();
        if (socket)
            this.console.log(`NeoLight talkback sent ${this.microphoneBytes} PCMU bytes to the native P2P bridge`);
    }
}

class NeoLightPlugin extends ScryptedDeviceBase implements DeviceProvider, Settings {
    private camera?: NeoLightCamera;
    private ringServer?: Server;

    get videoUrl(): string { return this.storage.getItem('videoUrl') || DEFAULT_VIDEO; }
    get talkPort(): number { return Number(this.storage.getItem('talkPort') || DEFAULT_TALK_PORT); }
    get ringPort(): number { return Number(this.storage.getItem('ringPort') || DEFAULT_RING_PORT); }

    constructor() {
        super();
        this.startRingServer();
        void this.discover();
    }

    private startRingServer(): void {
        this.ringServer = createServer((request, response) => {
            if (request.method !== 'POST' || request.url !== '/ring') {
                response.writeHead(404).end();
                return;
            }
            request.resume();
            (this.camera ||= new NeoLightCamera(this)).ring();
            response.writeHead(204).end();
        });
        this.ringServer.on('error', error => this.console.error('NeoLight ring receiver failed', error));
        this.ringServer.listen(this.ringPort, '127.0.0.1');
    }

    private async discover(): Promise<void> {
        const device: Device = {
            nativeId: DEVICE_ID,
            name: 'NeoLight Door',
            type: ScryptedDeviceType.Doorbell,
            interfaces: [ScryptedInterface.BinarySensor, ScryptedInterface.Camera, ScryptedInterface.VideoCamera, ScryptedInterface.Intercom],
            info: { manufacturer: 'NeoLight', model: 'ALPHA Hybrid' },
        };
        await deviceManager.onDevicesChanged({ devices: [device] });
    }

    async getDevice(nativeId: string): Promise<NeoLightCamera | undefined> {
        if (nativeId !== DEVICE_ID)
            return undefined;
        return this.camera ||= new NeoLightCamera(this);
    }

    async releaseDevice(_id: string, _nativeId: string): Promise<void> {
        await this.camera?.stopIntercom();
        this.camera?.release();
        this.camera = undefined;
    }

    async getSettings(): Promise<Setting[]> {
        return [
            { key: 'videoUrl', title: 'Video RTSP URL', value: this.videoUrl },
            { key: 'talkPort', title: 'P2P talk port', value: this.talkPort },
            { key: 'ringPort', title: 'Doorbell webhook port', value: this.ringPort },
        ];
    }

    async putSetting(key: string, value: SettingValue): Promise<void> {
        if (key === 'talkPort' || key === 'ringPort') {
            const port = Number(value);
            if (!Number.isInteger(port) || port < 1 || port > 65535)
                throw new Error('Invalid port');
            const changed = key === 'ringPort' && port !== this.ringPort;
            this.storage.setItem(key, String(port));
            if (changed) {
                this.ringServer?.close();
                this.startRingServer();
            }
            this.onDeviceEvent(ScryptedInterface.Settings, undefined);
            return;
        }
        if (key !== 'videoUrl')
            throw new Error('Unknown setting');
        const url = String(value);
        if (new URL(url).protocol !== 'rtsp:')
            throw new Error('RTSP URL required');
        this.storage.setItem(key, url);
        this.onDeviceEvent(ScryptedInterface.Settings, undefined);
    }
}

export default NeoLightPlugin;
