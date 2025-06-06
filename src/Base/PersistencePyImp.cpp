/***************************************************************************
 *   Copyright (c) 2007 Jürgen Riegel <juergen.riegel@web.de>              *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/


#include "PreCompiled.h"

#include <boost/iostreams/stream.hpp>

#include "Persistence.h"
#include "Writer.h"
#include <Base/PyWrapParseTupleAndKeywords.h>

// inclusion of the generated files (generated out of PersistencePy.pyi)
#include "PersistencePy.h"
#include "PersistencePy.cpp"

using namespace Base;

// returns a string which represent the object e.g. when printed in python
std::string PersistencePy::representation() const
{
    return {"<persistence object>"};
}


Py::String PersistencePy::getContent() const
{
    Base::StringWriter writer;
    // force all objects to write pure XML without files
    writer.setForceXML(true);
    getPersistencePtr()->Save(writer);

    return {writer.getString()};
}

Py::Long PersistencePy::getMemSize() const
{
    return Py::Long((long)getPersistencePtr()->getMemSize());
}

PyObject* PersistencePy::dumpContent(PyObject* args, PyObject* kwds) const
{
    int compression = 3;
    static const std::array<const char*, 2> kwds_def {"Compression", nullptr};
    PyErr_Clear();
    if (!Base::Wrapped_ParseTupleAndKeywords(args, kwds, "|i", kwds_def, &compression)) {
        return nullptr;
    }

    // setup the stream. the in flag is needed to make "read" work
    std::stringstream stream(std::stringstream::out | std::stringstream::in
                             | std::stringstream::binary);
    try {
        getPersistencePtr()->dumpToStream(stream, compression);
    }
    catch (Base::NotImplementedError&) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "Dumping content of this object type is not implemented");
        return nullptr;
    }
    catch (...) {
        PyErr_SetString(PyExc_IOError, "Unable to parse content into binary representation");
        return nullptr;
    }

    // build the byte array with correct size
    if (!stream.seekp(0, std::stringstream::end)) {
        PyErr_SetString(PyExc_IOError, "Unable to find end of stream");
        return nullptr;
    }

    std::stringstream::pos_type offset = stream.tellp();
    if (!stream.seekg(0, std::stringstream::beg)) {
        PyErr_SetString(PyExc_IOError, "Unable to find begin of stream");
        return nullptr;
    }

    PyObject* ba = PyByteArray_FromStringAndSize(nullptr, offset);

    // use the buffer protocol to access the underlying array and write into it
    Py_buffer buf = Py_buffer();
    PyObject_GetBuffer(ba, &buf, PyBUF_WRITABLE);
    try {
        if (!stream.read((char*)buf.buf, offset)) {
            PyErr_SetString(PyExc_IOError, "Error copying data into byte array");
            return nullptr;
        }
        PyBuffer_Release(&buf);
    }
    catch (...) {
        PyBuffer_Release(&buf);
        PyErr_SetString(PyExc_IOError, "Error copying data into byte array");
        return nullptr;
    }

    return ba;
}

PyObject* PersistencePy::restoreContent(PyObject* args)
{
    PyObject* buffer = nullptr;
    if (!PyArg_ParseTuple(args, "O", &buffer)) {
        return nullptr;
    }

    // check if it really is a buffer
    if (!PyObject_CheckBuffer(buffer)) {
        PyErr_SetString(PyExc_TypeError, "Must be a buffer object");
        return nullptr;
    }

    Py_buffer buf;
    if (PyObject_GetBuffer(buffer, &buf, PyBUF_SIMPLE) < 0) {
        return nullptr;
    }

    if (!PyBuffer_IsContiguous(&buf, 'C')) {
        PyErr_SetString(PyExc_TypeError, "Buffer must be contiguous");
        return nullptr;
    }

    // check if it really is a buffer
    try {
        using Device = boost::iostreams::basic_array_source<char>;
        boost::iostreams::stream<Device> stream((char*)buf.buf, buf.len);
        getPersistencePtr()->restoreFromStream(stream);
    }
    catch (...) {
        PyErr_SetString(PyExc_IOError, "Unable to restore content");
        return nullptr;
    }

    Py_Return;
}

PyObject* PersistencePy::getCustomAttributes(const char*) const
{
    return nullptr;
}

int PersistencePy::setCustomAttributes(const char*, PyObject*)
{
    return 0;
}
