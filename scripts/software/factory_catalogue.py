"""Print the verified native diagnostic catalogue without running any tests."""
import struct
from build_factory_debug import verified


def main():
    data = verified('jci/testdiag/svcjcitestdiag.so')
    # .data VA 0x76668, offset 0x6e668. g_testIDs: 58 uint32s;
    # g_testNames immediately follows: 58 fixed-size 50-byte strings.
    ids = struct.unpack_from('<58I', data, 0x6e66c)
    print('ID | Original name\n--- | ---')
    for index, test_id in enumerate(ids):
        slot = data[0x6e754 + index*50:0x6e754 + (index+1)*50]
        if b'\0' not in slot:
            raise ValueError('Unexpected diagnostic name layout')
        print(f'{test_id} | {slot.split(bytes([0]))[0].decode("ascii")}')


if __name__ == '__main__':
    main()
