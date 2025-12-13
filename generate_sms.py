#!/usr/bin/env python3
"""
Quick YTWL SMS Command Generator
Generate SMS commands for YTWL_CA10F device configuration
"""

def generate_sms_commands(server_host, server_port, apn="etnet"):
    """Generate SMS commands for YTWL device"""
    
    print("YTWL GPS Speed Limiter SMS Commands")
    print("=" * 50)
    print(f"Server: {server_host}:{server_port}")
    print(f"APN: {apn}")
    print("=" * 50)
    
    commands = [
        f"APN,1,{apn}#",
        f"SERVER,1,{server_host},{server_port}#",
        "CHECK#"
    ]
    
    print("\nSend these SMS commands to your YTWL_CA10F device:")
    print("\n1. Set APN:")
    print(f"   {commands[0]}")
    
    print("\n2. Set Server:")
    print(f"   {commands[1]}")
    
    print("\n3. Check Configuration:")
    print(f"   {commands[2]}")
    
    print("\n" + "=" * 50)
    print("INSTRUCTIONS:")
    print("1. Replace 'your-aws-ip' with your actual server IP")
    print("2. Send each command as a separate SMS to the device")
    print("3. Wait for confirmation between commands")
    print("4. Device should start sending GPS data to port 9000")
    print("=" * 50)
    
    return commands

def advanced_commands():
    """Additional useful commands"""
    print("\nADVANCED COMMANDS (optional):")
    print("-" * 30)
    
    advanced = [
        ("Set GPS update to 60 seconds", "INTERVAL,1,60#"),
        ("Set heartbeat to 5 minutes", "HEARTBEAT,1,300#"),
        ("Set timezone to Ethiopia (+3)", "TIMEZONE,1,3#"),
        ("Set default speed limit 80 km/h", "SPEEDLIMIT,1,80#"),
        ("Enable engine control", "ENGINE,1,ON#"),
        ("Get device status", "STATUS#"),
        ("Reboot device", "REBOOT,1#")
    ]
    
    for desc, cmd in advanced:
        print(f"{desc}:")
        print(f"   {cmd}")
        print()

if __name__ == "__main__":
    # Update these values
    YOUR_SERVER_IP = "your-aws-ip"  # Replace with your AWS IP or ngrok host
    YOUR_SERVER_PORT = "9000"
    YOUR_APN = "etnet"  # Ethiopian network APN
    
    # Generate basic commands
    generate_sms_commands(YOUR_SERVER_IP, YOUR_SERVER_PORT, YOUR_APN)
    
    # Show advanced options
    advanced_commands()
    
    print("\nFor testing with ngrok:")
    print("1. Run: ngrok tcp 9000")
    print("2. Use the ngrok hostname instead of your-aws-ip")
    print("3. Example: SERVER,1,4.tcp.ngrok.io,12345#")
