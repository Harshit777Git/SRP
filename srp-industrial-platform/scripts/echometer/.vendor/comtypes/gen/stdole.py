from enum import IntFlag

import comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 as __wrapper_module__
from comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 import (
    IPictureDisp, FONTITALIC, IEnumVARIANT, OLE_XSIZE_CONTAINER,
    typelib_path, DISPPARAMS, OLE_COLOR, DISPMETHOD, OLE_OPTEXCLUSIVE,
    BSTR, OLE_XSIZE_HIMETRIC, OLE_XSIZE_PIXELS, StdPicture, IFont,
    StdFont, Unchecked, _check_version, OLE_CANCELBOOL, Color,
    Default, FontEvents, OLE_XPOS_PIXELS, CoClass, OLE_XPOS_HIMETRIC,
    OLE_YPOS_PIXELS, Library, EXCEPINFO, OLE_HANDLE,
    FONTSTRIKETHROUGH, IPicture, GUID, OLE_YSIZE_HIMETRIC,
    OLE_YSIZE_PIXELS, FONTNAME, OLE_ENABLEDEFAULTBOOL, IDispatch,
    IFontEventsDisp, DISPPROPERTY, _lcid, FONTUNDERSCORE,
    OLE_XPOS_CONTAINER, Gray, OLE_YPOS_HIMETRIC, VARIANT_BOOL, Font,
    IFontDisp, Checked, FONTSIZE, Picture, OLE_YPOS_CONTAINER,
    VgaColor, Monochrome, COMMETHOD, dispid, FONTBOLD,
    OLE_YSIZE_CONTAINER, IUnknown, HRESULT
)


class OLE_TRISTATE(IntFlag):
    Unchecked = 0
    Checked = 1
    Gray = 2


class LoadPictureConstants(IntFlag):
    Default = 0
    Monochrome = 1
    VgaColor = 2
    Color = 4


__all__ = [
    'IPictureDisp', 'FONTITALIC', 'OLE_HANDLE', 'FONTSTRIKETHROUGH',
    'OLE_TRISTATE', 'IPicture', 'OLE_XSIZE_CONTAINER',
    'OLE_YSIZE_HIMETRIC', 'typelib_path', 'OLE_YSIZE_PIXELS',
    'FONTNAME', 'OLE_ENABLEDEFAULTBOOL', 'OLE_COLOR',
    'IFontEventsDisp', 'OLE_OPTEXCLUSIVE', 'OLE_XSIZE_HIMETRIC',
    'OLE_XSIZE_PIXELS', 'OLE_XPOS_HIMETRIC', 'FONTUNDERSCORE',
    'OLE_XPOS_CONTAINER', 'StdPicture', 'IFont', 'Gray', 'StdFont',
    'LoadPictureConstants', 'OLE_YPOS_HIMETRIC', 'Unchecked', 'Font',
    'IFontDisp', 'Checked', 'FONTSIZE', 'Picture',
    'OLE_YPOS_CONTAINER', 'VgaColor', 'Monochrome', 'OLE_CANCELBOOL',
    'Color', 'Default', 'FontEvents', 'OLE_XPOS_PIXELS', 'FONTBOLD',
    'OLE_YSIZE_CONTAINER', 'OLE_YPOS_PIXELS', 'Library'
]

