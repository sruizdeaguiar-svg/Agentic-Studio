import AppKit
let destination = CommandLine.arguments[1]
try FileManager.default.createDirectory(atPath: destination, withIntermediateDirectories: true)
for (name, size) in [("icon_16x16",16),("icon_16x16@2x",32),("icon_32x32",32),("icon_32x32@2x",64),("icon_128x128",128),("icon_128x128@2x",256),("icon_256x256",256),("icon_256x256@2x",512),("icon_512x512",512),("icon_512x512@2x",1024)] {
    let s = CGFloat(size)
    let opaque=CommandLine.arguments.contains("--ios")
    let alpha=opaque ? CGImageAlphaInfo.noneSkipLast : CGImageAlphaInfo.premultipliedLast
    let canvas=CGContext(data:nil,width:size,height:size,bitsPerComponent:8,bytesPerRow:size*4,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:alpha.rawValue)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current=NSGraphicsContext(cgContext:canvas,flipped:false)
    NSColor(calibratedRed:0.075,green:0.085,blue:0.16,alpha:1).setFill()
    if CommandLine.arguments.contains("--ios") { NSBezierPath(rect:NSRect(x:0,y:0,width:s,height:s)).fill() }
    NSBezierPath(roundedRect:NSRect(x:s*0.035,y:s*0.035,width:s*0.93,height:s*0.93),xRadius:s*0.21,yRadius:s*0.21).fill()
    let teal=NSColor(calibratedRed:0.32,green:0.91,blue:0.82,alpha:1)
    teal.setStroke()
    let links=NSBezierPath();links.lineWidth=s*0.078;links.lineCapStyle = .round;links.lineJoinStyle = .round
    links.move(to:NSPoint(x:s*0.24,y:s*0.25));links.line(to:NSPoint(x:s*0.50,y:s*0.76));links.line(to:NSPoint(x:s*0.76,y:s*0.25))
    links.move(to:NSPoint(x:s*0.35,y:s*0.43));links.line(to:NSPoint(x:s*0.65,y:s*0.43));links.stroke()
    for (x,y) in [(0.24,0.25),(0.50,0.76),(0.76,0.25)] {
        NSColor(calibratedRed:0.77,green:0.72,blue:1,alpha:1).setFill()
        NSBezierPath(ovalIn:NSRect(x:s*(x-0.066),y:s*(y-0.066),width:s*0.132,height:s*0.132)).fill()
    }
    NSGraphicsContext.restoreGraphicsState()
    let representation=NSBitmapImageRep(cgImage:canvas.makeImage()!)
    try representation.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:destination).appendingPathComponent(name+".png"))
}
