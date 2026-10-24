import Foundation
import Security
import CryptoKit

enum PinnedTrust {
    static func accepts(_ trust:SecTrust,host:String,pin:String)->Bool {
        guard pin.count==64,let chain=SecTrustCopyCertificateChain(trust) as? [SecCertificate],!chain.isEmpty,chain.count<=4,let leaf=chain.first,let anchor=chain.last else { return false }
        let digest=SHA256.hash(data:SecCertificateCopyData(leaf) as Data).map{String(format:"%02x",$0)}.joined()
        guard digest==pin.lowercased() else { return false }
        // Per-connection anchor only; never add a CA to the device's global trust store.
        guard SecTrustSetPolicies(trust,SecPolicyCreateSSL(true,host as CFString))==errSecSuccess,
              SecTrustSetAnchorCertificates(trust,[anchor] as CFArray)==errSecSuccess,
              SecTrustSetAnchorCertificatesOnly(trust,true)==errSecSuccess,
              SecTrustSetNetworkFetchAllowed(trust,false)==errSecSuccess else { return false }
        return SecTrustEvaluateWithError(trust,nil)
    }
}
