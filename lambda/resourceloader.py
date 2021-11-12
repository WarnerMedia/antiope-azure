#!/usr/bin/env python3
"""
primitive class for loading strings from uri named locations - will attempt to load complete
file or table into memory.

Required Parameters -
    src: A URI pointing to the source of the data

Exmample use:
    data = resourceloader(src="file:///home/users/me/xyz.json").getdata()
    data = resourceloader(src="s3://bucket/prefix/xyz.json").getdata()
    data = resourceloader(src="ddb://ddbtablename").getdata()

"""
import re
from pprint import pprint
import boto3
from botocore.exceptions import ClientError

class resourceloader(dict):
    """
        resouceloader is an attempt to normalize inputs from various types of storage.
        given a URI like s3://bucket/file or file:///home/user/myfile.txt or ddb://myddbtable
        will load the contents of the location into a string unless an object is returned.


        Optional Parameters-------------------------------------------------------------------
            :verbosity: optional bool value to print out debugging text
            :kwargs: The object takes undefined list of kwargs which subsiquent functions will
            make use of.
    """
    def __init__(self, src=None, **kwargs):
        """
            Initialize the "source" of the input data.
        """
        # add necessary properties to class
        self.setproperty( "src", src )
        self.setproperty( "file_read_mode", "" )

        # set any defaults
        self.verbosity = False

        # apply overrides given at initialization
        for kwarg in kwargs:
            self.setproperty( kwarg, kwargs[kwarg] )

        # set supported protocols
        self.setproperty( "protocols",{
                "file": self.load_from_disk,
                "s3": self.load_from_bucket,
                "ddb": self.load_from_ddb_table
                } )

        if self.src is not None:
            self.load()

    def load(self):
        # iterate protocols and execute respective loader
        for key in self.protocols.keys():
            proto = f'{key}://'
            if self.src.startswith( proto ):
                self.setproperty( "path", self.src.replace( proto, '', 1 ) )
                if self.verbosity:
                    print( f'Loading: {self.src}')
                self.protocols[key]()

    def list_protocols():
        return( self.protocols.keys() )

    def load_from_disk( self ):
        """
            Internal function to load data from local file system.
            data will be of type str
        """
        try:
            if self.file_read_mode != "":
                fd = open( self.path, str( self.file_read_mode ) )
            else:
                fd = open( self.path )
            self.setproperty( 'data', fd.read() )

        except Exception as e:
            print( f'{e} src={self.src}' )
            raise( e )


    def load_from_bucket(self):
        """
            Internal function to load file from s3.
            data will be of type bytes
        """
        client = boto3.client('s3')
        try:
            bucket = re.split( '/', self.path, 1 )[0]
            key = re.split( '/', self.path, 1)[1]
            response = client.get_object(
                Bucket=bucket,
                Key=key
            )
            self.setproperty( 'data', response['Body'].read() )

        except ClientError as e:
            print( f'{e} src={self.src}' )
            raise(e)

    def load_from_ddb_table(self):
        """
            Internal function to load data from dyamo db.
            data will be of type list
        """
        ddb = boto3.resource('dynamodb')
        try:
            table = ddb.Table(self.path)
            response = table.scan()
            data = []
            self.setproperty( 'data', data )
            while True:
                self.data.extend( response[ "Items" ] )
                if "LastEvaluatedKey" in response:
                    response = table.scan( ExclusiveStartKey=response['LastEvaluatedKey'], )
                else:
                    break

        except ClientError as e:
            print( f'{e} src={self.src}' )
            raise(e)

    def setproperty( self, key, val ):
        """
            Internal cheater function to normalize attribute and dictionary access.  This is not a python thing todo.
        """
        setattr( self, key, val )
        self[key] = val

    def getdata(self):
        """
            Returns the data loaded, during initialization, from specified location.
        """
        return( self.data )

if __name__ == '__main__':
    data = resourceloader( src="s3://warnermedia-antiope/Reports/account_inventory.json", verbosity=True).getdata()
    print( f'Length of loaded data = {len( data )} type of data = {type(data)}' )
    data = resourceloader( src="ddb://wm-scorecard-mailer-wmto-recipient-uuid-mapping", verbosity=True).getdata()
    print( f'Length of loaded data = {len( data )} type of data = {type(data)}' )
    data = resourceloader( src="file:///etc/hosts", verbosity=True).getdata()
    print( f'Length of loaded data = {len( data )} type of data = {type(data)}' )