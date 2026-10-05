import net from 'net';
import { randomBytes } from 'crypto';

type Response = { status: number; headers: Record<string, string> };

/** Minimal RTSP client for NeoLight's interleaved L16 return-audio track. */
export class RtspBackchannel {
    private socket?: net.Socket;
    private pending?: { resolve: (value: Response) => void; reject: (reason: Error) => void };
    private buffer = Buffer.alloc(0);
    private cseq = 0;
    private session = '';
    private sequence = 0;
    private sent = 0;
    private timestamp = 0;
    private readonly ssrc = randomBytes(4).readUInt32BE();
    private readonly url: URL;

    constructor(url: string) {
        this.url = new URL(url);
        if (this.url.protocol !== 'rtsp:')
            throw new Error('RTSP URL required');
    }

    get packetsSent(): number { return this.sent; }

    async connect(): Promise<void> {
        this.socket = net.createConnection(Number(this.url.port || 554), this.url.hostname);
        this.socket.on('data', chunk => this.onData(chunk));
        this.socket.on('error', error => this.pending?.reject(error));
        this.socket.on('close', () => this.pending?.reject(new Error('RTSP connection closed')));
        await new Promise<void>((resolve, reject) => {
            this.socket!.once('connect', resolve);
            this.socket!.once('error', reject);
        });
        try {
            await this.request('DESCRIBE', { Accept: 'application/sdp' });
            const setup = await this.request('SETUP', {
                Transport: 'RTP/AVP/TCP;unicast;interleaved=4-5',
            }, `${this.url.toString()}/backchannel`);
            this.session = setup.headers.session?.split(';')[0] || '';
            if (!this.session)
                throw new Error('RTSP SETUP did not return a session');
            await this.request('PLAY', { Session: this.session });
        }
        catch (error) {
            this.close();
            throw error;
        }
    }

    send(samples: Buffer): void {
        if (!this.socket || this.socket.destroyed || samples.length !== 480)
            return;
        const packet = Buffer.allocUnsafe(12 + samples.length);
        packet[0] = 0x80;
        packet[1] = 97;
        packet.writeUInt16BE(this.sequence++ & 0xffff, 2);
        packet.writeUInt32BE(this.timestamp >>> 0, 4);
        packet.writeUInt32BE(this.ssrc, 8);
        this.timestamp += 240;
        samples.copy(packet, 12);
        const header = Buffer.allocUnsafe(4);
        header[0] = 0x24;
        header[1] = 4;
        header.writeUInt16BE(packet.length, 2);
        this.socket.write(Buffer.concat([header, packet]));
        this.sent++;
    }

    close(): void {
        this.socket?.destroy();
        this.socket = undefined;
    }

    private async request(method: string, headers: Record<string, string>, url = this.url.toString()): Promise<Response> {
        if (!this.socket || this.pending)
            throw new Error('RTSP request already pending or disconnected');
        const cseq = ++this.cseq;
        const lines = [`${method} ${url} RTSP/1.0`, `CSeq: ${cseq}`, 'User-Agent: NeoLight-Intercom/0.1'];
        for (const [key, value] of Object.entries(headers))
            lines.push(`${key}: ${value}`);
        const response = new Promise<Response>((resolve, reject) => {
            this.pending = { resolve, reject };
            const timer = setTimeout(() => {
                if (this.pending) {
                    this.pending = undefined;
                    reject(new Error(`RTSP ${method} timed out`));
                }
            }, 10000);
            const wrapped = this.pending;
            this.pending = {
                resolve: value => { clearTimeout(timer); wrapped.resolve(value); },
                reject: error => { clearTimeout(timer); wrapped.reject(error); },
            };
        });
        this.socket.write(`${lines.join('\r\n')}\r\n\r\n`);
        const result = await response;
        if (result.status !== 200)
            throw new Error(`RTSP ${method} returned ${result.status}`);
        return result;
    }

    private onData(chunk: Buffer): void {
        this.buffer = Buffer.concat([this.buffer, chunk]);
        while (this.buffer.length) {
            // A media packet can arrive between RTSP responses. This client
            // only sends microphone audio and does not consume video/audio.
            if (this.buffer[0] === 0x24) {
                if (this.buffer.length < 4)
                    return;
                const length = this.buffer.readUInt16BE(2);
                if (this.buffer.length < 4 + length)
                    return;
                this.buffer = this.buffer.subarray(4 + length);
                continue;
            }
            const end = this.buffer.indexOf('\r\n\r\n');
            if (end < 0)
                return;
            const header = this.buffer.subarray(0, end).toString();
            const lines = header.split('\r\n');
            const status = Number(lines[0].match(/^RTSP\/1\.0 (\d+)/)?.[1]);
            const headers: Record<string, string> = {};
            for (const line of lines.slice(1)) {
                const colon = line.indexOf(':');
                if (colon >= 0)
                    headers[line.slice(0, colon).toLowerCase()] = line.slice(colon + 1).trim();
            }
            const bodyLength = Number(headers['content-length'] || 0);
            if (this.buffer.length < end + 4 + bodyLength)
                return;
            this.buffer = this.buffer.subarray(end + 4 + bodyLength);
            const pending = this.pending;
            this.pending = undefined;
            pending?.resolve({ status, headers });
        }
    }
}
