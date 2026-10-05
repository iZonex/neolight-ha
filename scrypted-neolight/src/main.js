// Scrypted's legacy plugin loader supplies runtime managers as globals.
// The server also sets a prerelease SDK module path which can return an
// uninitialized object during plugin startup. Use the runtime globals here.
delete process.env.SCRYPTED_SDK_MODULE;
delete process.env.SCRYPTED_SDK_CJS_MODULE;
delete process.env.SCRYPTED_SDK_ES_MODULE;
module.exports = require('./plugin.ts');
