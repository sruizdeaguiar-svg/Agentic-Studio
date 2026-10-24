import Foundation
import Security
final class Probe:NSObject,URLSessionDelegate {
    let host:String,pin:String
    var accepted=false
    init(_ host:String,_ pin:String) { self.host=host;self.pin=pin }
    func urlSession(_ session:URLSession,didReceive challenge:URLAuthenticationChallenge,completionHandler:@escaping(URLSession.AuthChallengeDisposition,URLCredential?)->Void) {
        guard challenge.protectionSpace.authenticationMethod==NSURLAuthenticationMethodServerTrust,challenge.protectionSpace.host==host,let trust=challenge.protectionSpace.serverTrust,PinnedTrust.accepts(trust,host:host,pin:pin) else { completionHandler(.cancelAuthenticationChallenge,nil);return }
        accepted=true;completionHandler(.useCredential,URLCredential(trust:trust))
    }
}
@main enum Main {
    static func main() {
        guard CommandLine.arguments.count==3,let url=URL(string:CommandLine.arguments[1]),let host=url.host else { exit(2) }
        let pin=CommandLine.arguments[2]
        func run(_ pin:String)->[String:Any] {
            let probe=Probe(host,pin),done=DispatchSemaphore(value:0)
            let session=URLSession(configuration:.ephemeral,delegate:probe,delegateQueue:nil)
            var status=0
            session.dataTask(with:url) { _,response,_ in status=(response as? HTTPURLResponse)?.statusCode ?? 0;done.signal() }.resume()
            _=done.wait(timeout:.now()+20);session.invalidateAndCancel();return ["trusted":probe.accepted,"status":status]
        }
        let good=run(pin),bad=run(String(repeating:"0",count:64))
        let passed=good["trusted"] as? Bool==true && good["status"] as? Int==401 && bad["trusted"] as? Bool==false && bad["status"] as? Int==0
        let output:[String:Any]=["passed":passed,"correct_pin":good,"wrong_pin":bad]
        if let data=try? JSONSerialization.data(withJSONObject:output,options:.sortedKeys),let text=String(data:data,encoding:.utf8) { print(text) }
        if !passed { exit(1) }
    }
}
