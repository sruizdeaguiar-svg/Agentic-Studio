import SwiftUI
import WebKit
import CryptoKit
import Security
import AVFoundation
import VisionKit

final class Connection: ObservableObject {
    @Published var url: URL?
    @Published var pin = ""
    @Published var message = "Vincula el iPhone o iPad con el QR mostrado en Conexiones del Mac."
    var origin: URL?
    func configure(_ text: String) {
        guard text.count<4096, let link=URLComponents(string:text.trimmingCharacters(in:.whitespacesAndNewlines)),link.scheme=="agenticstudio",link.host=="pair" else { message="Enlace de vinculación no válido.";return }
        let entries=link.queryItems ?? []
        guard Set(entries.map(\.name)).count==entries.count, let root=entries.first(where:{$0.name=="url"})?.value, let server=URLComponents(string:root),server.scheme=="https",let host=server.host,server.user==nil,server.password==nil,server.query==nil,server.fragment==nil,server.path.isEmpty || server.path=="/",let port=server.port,port>0,port<65536, let code=entries.first(where:{$0.name=="token"})?.value,code.count>=32,code.count<=128,code.allSatisfy({$0.isASCII && ($0.isLetter || $0.isNumber || $0=="_" || $0=="-")}),let digest=entries.first(where:{$0.name=="pin"})?.value,digest.count==64,digest.allSatisfy({$0.isHexDigit}) else { message="El QR no contiene servidor HTTPS, código y huella válidos.";return }
        let octets=host.split(separator:".").compactMap{Int($0)}
        let local=(octets.count==4 && octets.allSatisfy{$0>=0 && $0<=255} && (octets[0]==10 || octets[0]==127 || (octets[0]==192 && octets[1]==168) || (octets[0]==172 && octets[1]>=16 && octets[1]<=31)))
        guard local else { message="Solo se admiten direcciones IPv4 privadas de la red local.";return }
        var target=server;target.path="/";target.queryItems=[URLQueryItem(name:"pair",value:code)]
        origin=server.url;pin=digest.lowercased();url=target.url;message="Conectando al Mac con certificado verificado…"
    }
    func disconnect() { url=nil;origin=nil;pin="";message="Solicita un nuevo QR desde Conexiones del Mac." }
}

@main struct AgenticMobileApp: App {
    @StateObject var connection=Connection()
    var body: some Scene { WindowGroup { ContentView(connection:connection).onOpenURL{connection.configure($0.absoluteString)} } }
}
struct ContentView: View {
    @ObservedObject var connection: Connection
    @State private var pairing=""
    @State private var scan=false
    @Environment(\.scenePhase) private var scenePhase
    var body: some View {
        NavigationStack {
            Group {
                if let url=connection.url { VStack(spacing:0) { if !connection.message.isEmpty { Text(connection.message).font(.footnote).padding(8) };MacView(url:url,connection:connection).id(url) } }
                else {
                    VStack(alignment:.leading,spacing:20) {
                        Text("Agentic Studio").font(.largeTitle.bold())
                        Text("Versión \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "") · \(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "")").font(.caption).foregroundStyle(.secondary)
                        Text("El Mac ejecuta el modelo y las herramientas. Este dispositivo comparte su conversación sin descargar pesos.")
                        Text(connection.message).foregroundStyle(.secondary)
                        Text("Apunta al QR del Mac. La lectura es automática; no hace falta tomar una foto.").font(.footnote).foregroundStyle(.secondary)
                        Button("Escanear QR del Mac") { scan=true }.buttonStyle(.borderedProminent)
                        TextField("Pegar enlace agenticstudio://pair…",text:$pairing,axis:.vertical).textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                        Button("Vincular por enlace") { connection.configure(pairing);pairing="" }.buttonStyle(.bordered)
                        Text("Mac y dispositivo deben estar en la misma red. Activa Red local y muestra un QR desde Conexiones en el Mac. La vinculación aplica solo al proyecto elegido; requiere revisión según sus permisos.").font(.footnote).foregroundStyle(.secondary)
                        Spacer()
                    }.padding().frame(maxWidth:700)
                }
            }.navigationTitle(connection.origin?.host ?? "Agentic Studio").navigationBarTitleDisplayMode(.inline)
            .toolbar { if connection.url != nil { ToolbarItem(placement:.topBarTrailing) { Button("Desvincular") { connection.disconnect() } } } }
            .fullScreenCover(isPresented:$scan) {
                NavigationStack {
                    Scanner(found:{ result in scan=false;connection.configure(result) },cancelled:{ message in scan=false;if let message=message { connection.message=message } })
                        .ignoresSafeArea(edges:.bottom)
                        .navigationTitle("Escanear QR del Mac")
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar { ToolbarItem(placement:.topBarTrailing) { Button("Cerrar") { scan=false } } }
                }
            }
            .onChange(of:scenePhase) { _,phase in if phase == .background { scan=false } }
        }
    }
}
struct MacView: UIViewRepresentable {
    let url:URL
    @ObservedObject var connection:Connection
    func makeCoordinator()->Coordinator { Coordinator(connection) }
    func makeUIView(context:Context)->WKWebView {
        let configuration=WKWebViewConfiguration();configuration.websiteDataStore = .nonPersistent()
        let view=WKWebView(frame:.zero,configuration:configuration);view.navigationDelegate=context.coordinator;view.uiDelegate=context.coordinator;view.isInspectable=false
        view.load(URLRequest(url:url,cachePolicy:.reloadIgnoringLocalCacheData));return view
    }
    func updateUIView(_ view:WKWebView,context:Context) {}
    final class Coordinator:NSObject,WKNavigationDelegate,WKUIDelegate {
        let connection:Connection
        init(_ c:Connection) { connection=c }
        func webView(_ webView:WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void) {
            guard let u=navigationAction.request.url,let origin=connection.origin,u.scheme=="https",u.host==origin.host,u.port==origin.port else { decisionHandler(.cancel);return }
            decisionHandler(.allow)
        }
        func webView(_ webView:WKWebView,didReceive challenge:URLAuthenticationChallenge,completionHandler:@escaping(URLSession.AuthChallengeDisposition,URLCredential?)->Void) {
            guard challenge.protectionSpace.authenticationMethod==NSURLAuthenticationMethodServerTrust,let origin=connection.origin,challenge.protectionSpace.host==origin.host,challenge.protectionSpace.port==origin.port,let trust=challenge.protectionSpace.serverTrust,let host=origin.host else { completionHandler(.cancelAuthenticationChallenge,nil);return }
            guard PinnedTrust.accepts(trust,host:host,pin:connection.pin) else { connection.message="Certificado o huella no válidos. Solicita un nuevo QR en el Mac.";completionHandler(.cancelAuthenticationChallenge,nil);return }
            completionHandler(.useCredential,URLCredential(trust:trust))
        }
        func webView(_ webView:WKWebView,didFinish navigation:WKNavigation!) { connection.message="" }
        func webView(_ webView:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error) { connection.message=error.localizedDescription }
        func webView(_ webView:WKWebView,runJavaScriptConfirmPanelWithMessage message:String,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping(Bool)->Void) {
            guard let root=webView.window?.rootViewController else { completionHandler(false);return }
            let alert=UIAlertController(title:"Revisar acción del proyecto",message:message,preferredStyle:.alert);alert.addAction(UIAlertAction(title:"Cancelar",style:.cancel){_ in completionHandler(false)});alert.addAction(UIAlertAction(title:"Aprobar",style:.default){_ in completionHandler(true)});root.present(alert,animated:true)
        }
    }
}
struct Scanner:UIViewControllerRepresentable {
    let found:(String)->Void
    let cancelled:(String?)->Void
    func makeCoordinator()->Coordinator { Coordinator(found:found,cancelled:cancelled) }
    func makeUIViewController(context:Context)->UIViewController {
        guard DataScannerViewController.isSupported else {
            let empty=UIViewController();empty.view.backgroundColor = .systemBackground
            DispatchQueue.main.async { cancelled("Este dispositivo no permite el escáner de cámara. Usa el enlace de vinculación.") };return empty
        }
        let scanner=DataScannerViewController(recognizedDataTypes:[.barcode(symbologies:[.qr])],qualityLevel:.fast,recognizesMultipleItems:false,isHighFrameRateTrackingEnabled:false,isPinchToZoomEnabled:true,isGuidanceEnabled:true,isHighlightingEnabled:true)
        scanner.delegate=context.coordinator;context.coordinator.scanner=scanner
        return scanner
    }
    func updateUIViewController(_ controller:UIViewController,context:Context) {
        guard controller is DataScannerViewController else { return }
        context.coordinator.start()
    }
    static func dismantleUIViewController(_ controller:UIViewController,coordinator:Coordinator) { coordinator.stop() }
    @MainActor final class Coordinator:NSObject,DataScannerViewControllerDelegate {
        let found:(String)->Void
        let cancelled:(String?)->Void
        weak var scanner:DataScannerViewController?
        var task:Task<Void,Never>?
        var started=false
        var finished=false
        init(found:@escaping(String)->Void,cancelled:@escaping(String?)->Void) { self.found=found;self.cancelled=cancelled }
        func start() {
            guard !started,!finished else { return };started=true
            task=Task { @MainActor [weak self] in
                guard let self=self else { return }
                let granted=await AVCaptureDevice.requestAccess(for:.video)
                guard !Task.isCancelled,!self.finished else { return }
                guard granted,DataScannerViewController.isAvailable else { self.cancelled("Cámara no disponible o permiso denegado. Habilita Cámara en Ajustes → Agentic Studio, o usa el enlace. Si utilizas Device Hub, detén Screen Sharing antes de escanear.");return }
                do { try self.scanner?.startScanning() }
                catch { self.cancelled("No se pudo iniciar la cámara. Cierra el control remoto del iPad o utiliza el enlace de vinculación.") }
            }
        }
        func stop() { finished=true;task?.cancel();task=nil;scanner?.stopScanning();scanner?.delegate=nil;scanner=nil }
        func dataScanner(_ dataScanner:DataScannerViewController,didAdd addedItems:[RecognizedItem],allItems:[RecognizedItem]) {
            guard !finished else { return }
            for item in addedItems {
                if case .barcode(let barcode)=item,let value=barcode.payloadStringValue,value.hasPrefix("agenticstudio://pair?") {
                    stop();found(value);return
                }
            }
        }
        func dataScanner(_ dataScanner:DataScannerViewController,becameUnavailableWithError error:DataScannerViewController.ScanningUnavailable) {
            guard !finished else { return };stop();cancelled("La cámara dejó de estar disponible. Cierra el control remoto y vuelve a intentar, o usa el enlace.")
        }
    }
}
