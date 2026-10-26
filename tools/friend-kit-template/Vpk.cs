using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
public static class GemVpk {
 static string Z(BinaryReader r, long end) {
  var b = new List<byte>(); byte c;
  while(r.BaseStream.Position < end) { c=r.ReadByte(); if(c==0) return Encoding.UTF8.GetString(b.ToArray()); b.Add(c); }
  throw new InvalidDataException("Unterminated VPK string");
 }
 public static void Extract(string source, string target) {
  string root=Path.GetFullPath(target)+Path.DirectorySeparatorChar;
  var seen=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  using(var f=File.OpenRead(source)) using(var r=new BinaryReader(f)) {
   if(r.ReadUInt32()!=0x55AA1234 || r.ReadUInt32()!=2) throw new InvalidDataException("Expected VPK v2");
   long tree=r.ReadUInt32(), data=r.ReadUInt32();
   long chunks=r.ReadUInt32(), other=r.ReadUInt32(), signature=r.ReadUInt32();
   long end=28+tree;
   if(end+data+chunks+other+signature!=f.Length) throw new InvalidDataException("Invalid VPK size");
   string ext, dir, name;
   while((ext=Z(r,end))!="") while((dir=Z(r,end))!="") while((name=Z(r,end))!="") {
    r.ReadUInt32(); int preload=r.ReadUInt16(), archive=r.ReadUInt16();
    long offset=r.ReadUInt32(), length=r.ReadUInt32();
    if(r.ReadUInt16()!=65535 || f.Position+preload>end || (length>0 && (archive!=32767 || offset+length>data))) throw new InvalidDataException("Invalid VPK entry");
    string relative=(dir==" "?"":dir+"/")+name+(ext==" "?"":"."+ext);
    foreach(string part in relative.Split('/')) {
     if(part=="" || part=="." || part==".." || part.EndsWith(".") || part.EndsWith(" ") || part.IndexOfAny(Path.GetInvalidFileNameChars())>=0) throw new InvalidDataException("Unsafe path");
    }
    string path=Path.GetFullPath(Path.Combine(target,relative.Replace('/',Path.DirectorySeparatorChar)));
    if(!path.StartsWith(root,StringComparison.OrdinalIgnoreCase) || !seen.Add(path)) throw new InvalidDataException("Unsafe or duplicate path");
    byte[] pre=r.ReadBytes(preload); long resume=f.Position;
    Directory.CreateDirectory(Path.GetDirectoryName(path));
    using(var output=new FileStream(path,FileMode.CreateNew)) {
     output.Write(pre,0,pre.Length); f.Position=end+offset; byte[] buffer=new byte[1024*1024];
     while(length>0) { int n=f.Read(buffer,0,(int)Math.Min(buffer.Length,length)); if(n==0) throw new EndOfStreamException(); output.Write(buffer,0,n); length-=n; }
    }
    f.Position=resume;
   }
   if(f.Position!=end) throw new InvalidDataException("Invalid VPK directory length");
  }
 }
 public static void Patch(string path, long[] offsets, int[] lengths, string[] replacements) {
  byte[] data=File.ReadAllBytes(path);
  using(var output=new MemoryStream()) {
   long cursor=0;
   for(int i=0;i<offsets.Length;i++) {
    if(offsets[i]<cursor || offsets[i]+lengths[i]>data.Length) throw new InvalidDataException("Invalid patch range");
    output.Write(data,(int)cursor,(int)(offsets[i]-cursor)); byte[] value=Convert.FromBase64String(replacements[i]); output.Write(value,0,value.Length); cursor=offsets[i]+lengths[i];
   }
   output.Write(data,(int)cursor,data.Length-(int)cursor); File.WriteAllBytes(path,output.ToArray());
  }
 }
}
