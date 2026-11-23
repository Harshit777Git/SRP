import {createServer} from 'node:net';
import {Aedes} from 'aedes';
const broker = await Aedes.createBroker();
createServer({noDelay:true},broker.handle).listen(Number(process.env.MQTT_PORT??1883),'127.0.0.1',
  ()=>console.log('Local MQTT test broker ready'));
