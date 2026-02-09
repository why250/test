import pyvisa

def list_resources():
    try:
        rm = pyvisa.ResourceManager()
        print(f"VISA Backend: {rm.visalib}")
        resources = rm.list_resources()
        print("\nAvailable VISA Resources:")
        for res in resources:
            print(f"  - {res}")
            try:
                # 尝试打开资源获取 IDN，确认连接性
                # 注意：如果 NI MAX 打开，这里可能会失败
                with rm.open_resource(res) as inst:
                    print(f"    IDN: {inst.query('*IDN?').strip()}")
            except Exception as e:
                print(f"    Error querying IDN: {e}")
                
    except Exception as e:
        print(f"Error initializing VISA: {e}")
        print("Please ensure NI-VISA or PyVISA-py is installed.")

if __name__ == "__main__":
    list_resources()
