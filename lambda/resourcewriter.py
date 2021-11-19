#!/usr/bin/env python3
"""
primitive class for Writing strings from uri named locations - will attempt to load complete
file or table into memory.

Required Parameters -
    dst: A URI pointing to the source of the data

Exmample use:
    data = resourcewriter(dst="file:///home/users/me/xyz.json").getdata()
    data = resourcewriter(dst="s3://bucket/prefix/xyz.json").getdata()
    data = resourcewriter(dst="ddb://ddbtablename").getdata()

"""
import re
from pprint import pprint
import boto3
from botocore.exceptions import ClientError

class resourcewriter(dict):
    """
        resourcewriter is an attempt to normalize inputs from various types of storage.
        given a URI like s3://bucket/file or file:///home/user/myfile.txt or ddb://myddbtable
        will load the contents of the location into a string unless an object is returned.


        Optional Parameters-------------------------------------------------------------------
            :verbosity: optional bool value to print out debugging text
            :kwargs: The object takes undefined list of kwargs which subsiquent functions will
            make use of.
    """
    def __init__(self, dst=None, **kwargs):
        """
            Initialize the "source" of the input data.
        """
        # add necessary properties to class
        self.setproperty( "dst", dst )
        self.filewritemode = "w"
        # set any defaults
        self.verbosity = False

        # apply overrides given at initialization
        for kwarg in kwargs:
            self.setproperty( kwarg, kwargs[kwarg] )


    def writedata( self, data ):
        # set supported protocols
        protocols = {
                "file": self.write_to_disk,
                "s3": self.write_to_bucket,
                "ddb": self.write_to_ddb_table
                }

        self.setproperty( "data", data )

        # iterate protocols and execute respective loader
        for key in protocols.keys():
            proto = f'{key}://'
            if self.dst.startswith( proto ):
                self.setproperty( "path", self.dst.replace( proto, '', 1 ) )
                if self.verbosity:
                    print( f'Writing: {self.dst}')
                protocols[key]()

    def write_to_disk(self):
        """
            Internal function to load data from local file system.
            data will be of type str
        """
        # set the write mode for various objects.
        if type( self.data ) is memoryview:
            self.filewritemode = "wb"

        try:
            with open(self.path, str( self.filewritemode )) as fd:
                fd.write(self.data)
        except Exception as e:
            print( f'{e} dst={self.dst}' )
            raise( e )


    def write_to_bucket(self):
        """
            Internal function to load file from s3.
            data will be of type bytes
        """
        client = boto3.client('s3')
        try:
            bucket = re.split( '/', self.path, 1 )[0]
            key = re.split( '/', self.path, 1)[1]
            if type( self.data ) is memoryview:
                body = self.data.tobytes()
            else:
                body = self.data
            response = client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body
            )
        except ClientError as e:
            print( f'{e} dst={self.dst}' )
            raise(e)

    def write_to_ddb_table(self):
        """
            Internal function to write data from dynamo db.
            data will be of type list
        """
        try:
            ddb = boto3.resource('dynamodb')
            table = ddb.Table(self.path)
            if type( self.data ) is dict:
                table.put_item( Item=self.data )
                print( "wrote 1 item")
            else:
                for item in self.data:
                    table.put_item( Item=item )
                print( f'wrote {len(self.data)} items')

        except ClientError as e:
            print( f'{e} dst={self.dst}' )
            raise(e)

    def setproperty( self, key, val ):
        """
            Internal cheater function to normalize attribute and dictionary access.  This is not a python thing todo.
        """
        setattr( self, key, val )
        self[key] = val

    def setdata(self, data):
        """
            sets the data to be written, during initialization, from specified location.
        """
        self.setproperty( "data", data )

if __name__ == '__main__':
    # data = resourcewriter( dst="s3://warnermedia-antiope/Reports/account_inventory.json", verbosity=True).getdata()
    # data = resourcewriter( dst="ddb://wm-scorecard-mailer-wmto-recipient-uuid-mapping", verbosity=True).getdata()
    rw = resourcewriter( dst="s3://dch-allusers-acl-bucet/dch.txt", verbosity=True).writedata( "MickeyMouse")

    #print( f'Length of loaded data = {len( data )} type of data = {type(data)}' )